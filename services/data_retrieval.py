"""
Karma Kadabra V2 — Data Retrieval Service

Downloads purchased data from sellers after escrow completes.

Three retrieval strategies (tried in order):
  1. S3 direct: Download from seller's known S3 prefix (KK agents only,
     all run in the same AWS account with shared IAM role).
  2. Submission evidence: Parse delivery_url from seller's submitted evidence.
  3. Approval notes: Parse presigned URL from task approval notes.

All downloaded data is saved to data/purchases/ where the processing
pipelines (process_skills, process_voices, process_souls) expect it.

State is persisted in data/.retrieval_state.json to avoid re-downloading.
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from services.em_client import EMClient
except ImportError:
    from em_client import EMClient

logger = logging.getLogger("kk.data_retrieval")

S3_BUCKET = "karmacadabra-agent-data"
S3_REGION = "us-east-1"

# ---------------------------------------------------------------------------
# Product classification — maps task title keywords to output directories
# ---------------------------------------------------------------------------

PRODUCT_ROUTING: list[tuple[list[str], dict[str, str]]] = [
    # Order matters: more specific patterns first
    (["soul", "complete profile"], {"type": "soul_profiles", "subdir": "purchases"}),
    (["skill"], {"type": "skill_profiles", "subdir": "purchases"}),
    (["personality", "voice"], {"type": "voice_profiles", "subdir": "purchases"}),
    (["raw", "log", "chat"], {"type": "raw_logs", "subdir": "purchases"}),
]

# ---------------------------------------------------------------------------
# KK agent S3 prefixes — for direct download between swarm agents
# ---------------------------------------------------------------------------

# Map seller agent name (from task title/metadata) to S3 prefixes to search
_SELLER_S3_PREFIXES: dict[str, list[str]] = {
    "kk-karma-hello": [
        "kk-karma-hello/deliveries/",
        "kk-karma-hello/logs/",
    ],
    "kk-skill-extractor": [
        "kk-skill-extractor/deliveries/",
        "kk-skill-extractor/skills/",
    ],
    "kk-voice-extractor": [
        "kk-voice-extractor/deliveries/",
        "kk-voice-extractor/voices/",
    ],
    "kk-soul-extractor": [
        "kk-soul-extractor/deliveries/",
        "kk-soul-extractor/souls/",
    ],
}


def _classify_product(title: str) -> dict[str, str]:
    """Classify a task into product type and output subdirectory."""
    title_lower = title.lower()
    for keywords, info in PRODUCT_ROUTING:
        if any(kw in title_lower for kw in keywords):
            return info
    return {"type": "unknown", "subdir": "purchases"}


def _infer_seller(title: str) -> str:
    """Infer seller agent name from task title."""
    title_lower = title.lower()
    if any(kw in title_lower for kw in ["raw", "log", "chat"]):
        return "kk-karma-hello"
    if "skill" in title_lower:
        return "kk-skill-extractor"
    if any(kw in title_lower for kw in ["personality", "voice"]):
        return "kk-voice-extractor"
    if any(kw in title_lower for kw in ["soul", "complete profile"]):
        return "kk-soul-extractor"
    return ""


def _extract_url(text: str) -> str | None:
    """Extract first HTTPS URL from text."""
    m = re.search(r"https?://\S+", text)
    return m.group(0).rstrip(".,;)\"'") if m else None


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------


def _load_state(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"retrieved": {}}


def _save_state(path: Path, state: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError as e:
        logger.error(f"Failed to save retrieval state: {e}")


# ---------------------------------------------------------------------------
# Strategy 1: S3 direct download
# ---------------------------------------------------------------------------


def _download_from_s3(seller: str, product_type: str) -> Any | None:
    """Download latest delivery file from seller's S3 prefix.

    Returns parsed JSON data (dict or list), or None on failure.
    """
    prefixes = _SELLER_S3_PREFIXES.get(seller, [])
    if not prefixes:
        return None

    try:
        import boto3

        s3 = boto3.client("s3", region_name=S3_REGION)

        for prefix in prefixes:
            try:
                resp = s3.list_objects_v2(
                    Bucket=S3_BUCKET,
                    Prefix=prefix,
                    MaxKeys=50,
                )
            except Exception:
                continue

            objects = resp.get("Contents", [])
            if not objects:
                continue

            # Filter to JSON files only
            json_objects = [o for o in objects if o["Key"].endswith(".json")]
            if not json_objects:
                continue

            # Get the most recent file
            latest = sorted(json_objects, key=lambda o: o["LastModified"])[-1]
            s3_key = latest["Key"]

            try:
                obj = s3.get_object(Bucket=S3_BUCKET, Key=s3_key)
                body = obj["Body"].read()

                # Guard against very large files (>50 MB) on t3.small
                if len(body) > 50 * 1024 * 1024:
                    logger.warning(
                        f"S3 object too large ({len(body)} bytes): {s3_key}"
                    )
                    return None

                data = json.loads(body.decode("utf-8"))
                logger.info(
                    f"S3 download OK: {s3_key} ({len(body):,} bytes)"
                )
                return data
            except json.JSONDecodeError:
                logger.warning(f"S3 object not valid JSON: {s3_key}")
            except Exception as e:
                logger.debug(f"S3 get_object failed for {s3_key}: {e}")

        return None
    except ImportError:
        logger.debug("boto3 not available for S3 direct download")
        return None
    except Exception as e:
        logger.debug(f"S3 download error for seller {seller}: {e}")
        return None


# ---------------------------------------------------------------------------
# Strategy 2: Fetch presigned URL via HTTP
# ---------------------------------------------------------------------------


async def _fetch_presigned_url(url: str) -> Any | None:
    """HTTP GET a presigned URL and parse JSON response."""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as http:
            resp = await http.get(url)
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"URL fetch OK ({len(resp.content):,} bytes)")
            return data
    except Exception as e:
        logger.debug(f"URL fetch failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Strategy 3: Parse delivery info from EM API
# ---------------------------------------------------------------------------


async def _get_delivery_url_from_submissions(
    client: EMClient, task_id: str
) -> str | None:
    """Check submission evidence for a delivery_url field."""
    try:
        submissions = await client.get_submissions(task_id)
        for sub in submissions:
            evidence = sub.get("evidence", {})
            if isinstance(evidence, dict):
                jr = evidence.get("json_response", {})
                if isinstance(jr, dict):
                    url = jr.get("delivery_url", "")
                    if url and url.startswith("http"):
                        return url
                    # Also check s3_key — we can generate URL from it
                    s3_key = jr.get("s3_key", "")
                    if s3_key:
                        return f"s3://{S3_BUCKET}/{s3_key}"
    except Exception as e:
        logger.debug(f"get_submissions for delivery URL: {e}")
    return None


async def _get_delivery_url_from_task(
    client: EMClient, task_id: str
) -> str | None:
    """Check task details/notes for a delivery URL."""
    try:
        task_data = await client.get_task(task_id)
        # Check various fields that might contain the URL
        for field_name in ("notes", "approval_notes", "review_notes", "completion_notes"):
            text = task_data.get(field_name, "")
            if text:
                url = _extract_url(text)
                if url:
                    return url
    except Exception as e:
        logger.debug(f"get_task for delivery URL: {e}")
    return None


# ---------------------------------------------------------------------------
# Main retrieval function
# ---------------------------------------------------------------------------


async def check_and_retrieve_all(
    client: EMClient,
    data_dir: Path,
    wallet_address: str,
) -> list[dict]:
    """Check for completed purchases and download delivered data.

    Tries three strategies in order:
      1. S3 direct download (KK agents share bucket via IAM role)
      2. Parse delivery_url from submission evidence
      3. Parse delivery_url from task notes

    All data is saved to data/purchases/{product_type}_{task_id}.json
    where the processing pipelines expect it.

    Args:
        client: EM API client.
        data_dir: Base data directory (e.g., /app/data).
        wallet_address: This agent's wallet address.

    Returns:
        List of retrieved file descriptors.
    """
    retrieved: list[dict] = []
    state_file = data_dir / ".retrieval_state.json"
    state = _load_state(state_file)

    try:
        # List completed tasks where this agent was the executor (buyer)
        completed_tasks = await client.list_tasks(
            agent_wallet=wallet_address,
            status="completed",
        )

        if not completed_tasks:
            return retrieved

        purchases_dir = data_dir / "purchases"
        purchases_dir.mkdir(parents=True, exist_ok=True)

        for task in completed_tasks:
            task_id = task.get("id", "")
            title = task.get("title", "unknown")

            if not task_id:
                continue

            # Skip already retrieved
            if task_id in state.get("retrieved", {}):
                continue

            product = _classify_product(title)
            seller = _infer_seller(title)
            data = None

            # Strategy 1: S3 direct download
            if seller:
                data = _download_from_s3(seller, product["type"])
                if data is not None:
                    logger.info(f"Strategy 1 (S3 direct) succeeded for: {title}")

            # Strategy 2: Delivery URL from submission evidence
            if data is None:
                url = await _get_delivery_url_from_submissions(client, task_id)
                if url:
                    if url.startswith("s3://"):
                        # Parse S3 URI and download directly
                        s3_key = url.replace(f"s3://{S3_BUCKET}/", "")
                        data = _download_s3_key(s3_key)
                    else:
                        data = await _fetch_presigned_url(url)
                    if data is not None:
                        logger.info(
                            f"Strategy 2 (submission URL) succeeded for: {title}"
                        )

            # Strategy 3: Delivery URL from task notes
            if data is None:
                url = await _get_delivery_url_from_task(client, task_id)
                if url:
                    data = await _fetch_presigned_url(url)
                    if data is not None:
                        logger.info(
                            f"Strategy 3 (task notes URL) succeeded for: {title}"
                        )

            if data is None:
                logger.warning(
                    f"All retrieval strategies failed for: {title} ({task_id[:8]})"
                )
                continue

            # Save to purchases directory
            output_file = purchases_dir / f"{product['type']}_{task_id[:8]}.json"
            try:
                content = json.dumps(data, ensure_ascii=False)
                output_file.write_text(content, encoding="utf-8")
            except (TypeError, OSError) as e:
                logger.error(f"Failed to save retrieved data: {e}")
                continue

            file_size = output_file.stat().st_size

            # Mark as retrieved
            state.setdefault("retrieved", {})[task_id] = {
                "title": title,
                "product_type": product["type"],
                "seller": seller,
                "file": str(output_file),
                "size_bytes": file_size,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            }

            retrieved.append(
                {
                    "task_id": task_id,
                    "title": title,
                    "file": str(output_file),
                    "product_type": product["type"],
                    "size_bytes": file_size,
                }
            )
            logger.info(
                f"Retrieved: {title} -> {output_file.name} ({file_size:,} bytes)"
            )

    except Exception as e:
        logger.error(f"check_and_retrieve_all error: {e}")
    finally:
        _save_state(state_file, state)

    return retrieved


# ---------------------------------------------------------------------------
# Helper: download a specific S3 key
# ---------------------------------------------------------------------------


def _download_s3_key(s3_key: str) -> Any | None:
    """Download a specific S3 key and parse as JSON."""
    try:
        import boto3

        s3 = boto3.client("s3", region_name=S3_REGION)
        obj = s3.get_object(Bucket=S3_BUCKET, Key=s3_key)
        body = obj["Body"].read().decode("utf-8")
        return json.loads(body)
    except Exception as e:
        logger.debug(f"S3 key download failed ({s3_key}): {e}")
        return None
