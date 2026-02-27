"""
Karma Kadabra V2 — Data Delivery Service

Generates S3 presigned URLs for delivering purchased data products.
When a buyer pays for data (e.g., chat logs from karma-hello), this
service generates a time-limited download URL for the data.

Usage:
    from services.data_delivery import generate_delivery_url, prepare_delivery_package

    # Generate URL for a specific product
    url = generate_delivery_url("kk-karma-hello", "logs/chat_logs_20260227.json")

    # Prepare a delivery package (aggregate multiple files)
    url = await prepare_delivery_package("kk-karma-hello", "raw_logs", data_dir)
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("kk.data-delivery")

S3_BUCKET = "karmacadabra-agent-data"
S3_REGION = "us-east-1"
PRESIGNED_EXPIRY = 3600  # 1 hour


def _get_s3_client():
    """Get boto3 S3 client."""
    import boto3
    return boto3.client("s3", region_name=S3_REGION)


def generate_delivery_url(
    agent_name: str,
    s3_key_suffix: str,
    expiry: int = PRESIGNED_EXPIRY,
) -> str | None:
    """Generate a presigned URL for an S3 object.

    Args:
        agent_name: Agent name (S3 prefix, e.g., "kk-karma-hello").
        s3_key_suffix: Path within agent's S3 folder (e.g., "logs/chat_logs_20260227.json").
        expiry: URL expiry in seconds (default: 1 hour).

    Returns:
        Presigned URL string, or None on failure.
    """
    s3_key = f"{agent_name}/{s3_key_suffix}"

    try:
        s3 = _get_s3_client()

        # Verify object exists
        try:
            s3.head_object(Bucket=S3_BUCKET, Key=s3_key)
        except s3.exceptions.ClientError:
            logger.error(f"S3 object not found: s3://{S3_BUCKET}/{s3_key}")
            return None

        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": s3_key},
            ExpiresIn=expiry,
        )
        logger.info(f"Generated presigned URL for {s3_key} (expires in {expiry}s)")
        return url

    except Exception as e:
        logger.error(f"Failed to generate presigned URL: {e}")
        return None


async def prepare_delivery_package(
    agent_name: str,
    product_key: str,
    data_dir: Path,
    expiry: int = PRESIGNED_EXPIRY,
) -> str | None:
    """Prepare and upload a delivery package, return presigned URL.

    For products that need aggregation (e.g., "raw_logs" bundles the
    aggregated.json), this uploads the package to S3 and returns a
    presigned URL.

    Args:
        agent_name: Agent name.
        product_key: Product identifier (e.g., "raw_logs", "user_stats").
        data_dir: Local data directory.
        expiry: URL expiry in seconds.

    Returns:
        Presigned URL string, or None on failure.
    """
    # Map product keys to their data sources
    product_sources = {
        "raw_logs": "aggregated.json",
        "user_stats": "user-stats.json",
        "topic_map": "topic-analysis.json",
        "skill_profile": "skill-profiles.json",
    }

    source_file = product_sources.get(product_key)
    if not source_file:
        logger.error(f"Unknown product key: {product_key}")
        return None

    local_path = data_dir / source_file
    if not local_path.exists():
        logger.warning(f"Product data not found: {local_path}")
        # Fall back to serving individual log files
        if product_key == "raw_logs":
            return _serve_latest_logs(agent_name, expiry)
        return None

    # Upload delivery package to S3
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    s3_key = f"{agent_name}/deliveries/{product_key}_{ts}.json"

    try:
        s3 = _get_s3_client()
        body = local_path.read_text(encoding="utf-8")

        s3.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=body.encode("utf-8"),
            ContentType="application/json",
        )
        logger.info(f"Uploaded delivery package: s3://{S3_BUCKET}/{s3_key}")

        # Generate presigned URL
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": s3_key},
            ExpiresIn=expiry,
        )
        return url

    except Exception as e:
        logger.error(f"Failed to prepare delivery: {e}")
        return None


def _serve_latest_logs(agent_name: str, expiry: int) -> str | None:
    """Serve the most recent log file from S3 as fallback."""
    try:
        s3 = _get_s3_client()
        prefix = f"{agent_name}/logs/"

        resp = s3.list_objects_v2(
            Bucket=S3_BUCKET,
            Prefix=prefix,
            MaxKeys=100,
        )
        objects = resp.get("Contents", [])
        if not objects:
            logger.warning(f"No log files found in s3://{S3_BUCKET}/{prefix}")
            return None

        # Get the most recent file
        latest = sorted(objects, key=lambda o: o["LastModified"])[-1]
        s3_key = latest["Key"]

        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": s3_key},
            ExpiresIn=expiry,
        )
        logger.info(f"Serving latest log: {s3_key}")
        return url

    except Exception as e:
        logger.error(f"Failed to serve latest logs: {e}")
        return None
