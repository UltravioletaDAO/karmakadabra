"""
Karma Kadabra V2 — Data Retrieval Service

After a buyer agent purchases data on Execution Market and the seller
approves the submission, this service retrieves the delivered data.

The delivery URL is embedded in the approval notes by the seller
(via data_delivery.py). This module:

  1. Polls task status for completion
  2. Extracts delivery URL from approval notes
  3. Downloads the data to data/purchases/
  4. Returns the local path for the buyer to process

Usage:
    from services.data_retrieval import retrieve_purchased_data

    result = await retrieve_purchased_data(client, task_id, data_dir)
    if result:
        print(f"Data saved to: {result['local_path']}")
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx

logger = logging.getLogger("kk.data-retrieval")

# Regex to find S3 presigned URLs in approval notes
URL_PATTERN = re.compile(r"https://[\w.-]+\.s3[\w.-]*\.amazonaws\.com/[^\s\"']+")


async def retrieve_purchased_data(
    client,
    task_id: str,
    data_dir: Path,
    timeout: float = 30.0,
) -> dict | None:
    """Retrieve data from a completed purchase.

    Args:
        client: EMClient instance.
        task_id: The task ID that was purchased.
        data_dir: Base data directory for saving downloaded files.
        timeout: HTTP download timeout.

    Returns:
        Dict with {task_id, local_path, size_bytes} or None on failure.
    """
    purchases_dir = data_dir / "purchases"
    purchases_dir.mkdir(parents=True, exist_ok=True)

    # Get task details
    try:
        task = await client.get_task(task_id)
    except Exception as e:
        logger.error(f"Failed to get task {task_id}: {e}")
        return None

    status = task.get("status", "")
    if status not in ("completed", "approved"):
        logger.info(f"Task {task_id} status is '{status}' — not ready for retrieval")
        return None

    # Look for delivery URL in submissions/approvals
    delivery_url = None
    try:
        submissions = await client.get_submissions(task_id)
        for sub in submissions:
            # Check approval notes for presigned URL
            notes = sub.get("notes", "") or sub.get("review_notes", "")
            evidence = sub.get("evidence", {})
            if isinstance(evidence, dict):
                notes += " " + evidence.get("notes", "")

            urls = URL_PATTERN.findall(notes)
            if urls:
                delivery_url = urls[0]
                break

            # Also check evidence_url field
            ev_url = sub.get("evidence_url", "")
            if ev_url and "s3" in ev_url and "amazonaws" in ev_url:
                delivery_url = ev_url
                break
    except Exception as e:
        logger.error(f"Failed to get submissions for {task_id}: {e}")
        return None

    if not delivery_url:
        logger.warning(f"No delivery URL found for task {task_id}")
        return None

    # Download the data
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    title = task.get("title", "unknown").replace(" ", "_")[:40]
    filename = f"{task_id[:8]}_{title}_{ts}.json"
    local_path = purchases_dir / filename

    try:
        async with httpx.AsyncClient(timeout=timeout, verify=False) as http:
            resp = await http.get(delivery_url)
            resp.raise_for_status()

            local_path.write_bytes(resp.content)
            size = len(resp.content)
            logger.info(f"Downloaded {size:,} bytes -> {local_path.name}")

            return {
                "task_id": task_id,
                "local_path": str(local_path),
                "size_bytes": size,
                "filename": filename,
            }

    except Exception as e:
        logger.error(f"Download failed for task {task_id}: {e}")
        return None


async def check_and_retrieve_all(
    client,
    data_dir: Path,
    agent_wallet: str,
) -> list[dict]:
    """Check all applied/completed tasks and retrieve any available data.

    Returns list of retrieval results.
    """
    results = []

    try:
        # Check completed tasks where we were the buyer
        tasks = await client.list_tasks(
            agent_wallet=agent_wallet,
            status="completed",
        )

        for task in tasks:
            task_id = task.get("id", "")
            title = task.get("title", "")

            # Only retrieve KK Data tasks
            if "[KK Data]" not in title:
                continue

            # Check if already downloaded
            purchases_dir = data_dir / "purchases"
            existing = list(purchases_dir.glob(f"{task_id[:8]}_*")) if purchases_dir.exists() else []
            if existing:
                continue

            result = await retrieve_purchased_data(client, task_id, data_dir)
            if result:
                results.append(result)

    except Exception as e:
        logger.error(f"Retrieval scan failed: {e}")

    return results
