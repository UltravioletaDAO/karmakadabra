"""Data retrieval service for buyer agents.

Checks for completed purchases and retrieves delivered data files.
"""

import logging
from pathlib import Path

from services.em_client import EMClient

logger = logging.getLogger("kk.data_retrieval")


async def check_and_retrieve_all(
    client: EMClient,
    data_dir: Path,
    wallet_address: str,
) -> list[dict]:
    """Check for completed purchases and retrieve any delivered data.

    Args:
        client: The EM API client.
        data_dir: Base data directory for storing retrieved files.
        wallet_address: The agent's wallet address to filter purchases.

    Returns:
        List of dicts describing retrieved files, empty if none.
    """
    retrieved = []

    try:
        # List tasks where this agent is the executor and status is completed
        completed_tasks = await client.list_tasks(
            executor_wallet=wallet_address,
            status="completed",
        )

        if not completed_tasks:
            return retrieved

        retrieval_dir = data_dir / "retrieved"
        retrieval_dir.mkdir(parents=True, exist_ok=True)

        for task in completed_tasks:
            task_id = task.get("id", "")
            title = task.get("title", "unknown")

            # Check if already retrieved
            marker = retrieval_dir / f"{task_id}.done"
            if marker.exists():
                continue

            # Try to get task details with delivery data
            try:
                task_data = await client.get_task(task_id)
                delivery = task_data.get("delivery", {})

                if delivery:
                    # Save delivery data
                    import json

                    output_file = retrieval_dir / f"{task_id}.json"
                    output_file.write_text(
                        json.dumps(delivery, indent=2), encoding="utf-8"
                    )

                    # Mark as retrieved
                    marker.write_text(task_id, encoding="utf-8")

                    retrieved.append(
                        {
                            "task_id": task_id,
                            "title": title,
                            "file": str(output_file),
                        }
                    )
                    logger.info(f"  Retrieved data for task: {title} ({task_id})")
            except Exception as e:
                logger.debug(f"  Retrieval failed for {task_id}: {e}")

    except Exception as e:
        logger.debug(f"  check_and_retrieve_all error: {e}")

    return retrieved
