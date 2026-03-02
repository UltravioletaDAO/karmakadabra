"""Purchase tracker to prevent duplicate agent purchases on Execution Market."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("kk.purchase_tracker")


class PurchaseTracker:
    """Tracks what each agent has bought to prevent duplicate purchases.

    State is persisted in a JSON file at data_dir/purchase_history.json.
    """

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.state_file = self.data_dir / "purchase_history.json"
        self._state = self._load()

    def _load(self) -> dict[str, Any]:
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load purchase history: %s", e)
        return {"purchases": [], "version": 1}

    def _save(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(
            json.dumps(self._state, indent=2, default=str),
            encoding="utf-8",
        )

    def already_bought(self, task_id: str) -> bool:
        """Check if we already bought/applied to this specific task."""
        return any(p["task_id"] == task_id for p in self._state["purchases"])

    def record_purchase(
        self,
        task_id: str,
        seller: str,
        product_type: str,
        price_usd: float,
        title: str = "",
    ) -> None:
        """Record a purchase. Idempotent -- skips if task_id already tracked."""
        if self.already_bought(task_id):
            return
        self._state["purchases"].append({
            "task_id": task_id,
            "seller": seller,
            "product_type": product_type,
            "price_usd": price_usd,
            "title": title,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self._save()
        logger.info("Recorded purchase: %s from %s ($%.4f)", task_id[:8], seller, price_usd)

    def get_history(
        self,
        product_type: str | None = None,
        seller: str | None = None,
        hours: float | None = None,
    ) -> list[dict[str, Any]]:
        """Get purchase history with optional filters."""
        results = self._state["purchases"]
        if product_type:
            results = [p for p in results if p.get("product_type") == product_type]
        if seller:
            results = [p for p in results if p.get("seller") == seller]
        if hours:
            cutoff = datetime.now(timezone.utc).timestamp() - (hours * 3600)
            results = [
                p for p in results
                if datetime.fromisoformat(p["timestamp"]).timestamp() > cutoff
            ]
        return results

    def daily_spend(self) -> float:
        """Total USD spent today."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return sum(
            p["price_usd"]
            for p in self._state["purchases"]
            if p["timestamp"].startswith(today)
        )

    def needs_product(self, product_type: str, max_age_hours: float = 2.0) -> bool:
        """Check if we need a product (don't have a recent one)."""
        recent = self.get_history(product_type=product_type, hours=max_age_hours)
        return len(recent) == 0

    def total_purchases(self) -> int:
        """Total number of purchases ever."""
        return len(self._state["purchases"])

    def summary(self) -> dict[str, Any]:
        """Get a summary of purchase activity."""
        today_spend = self.daily_spend()
        total = self.total_purchases()
        by_type: dict[str, int] = {}
        for p in self._state["purchases"]:
            pt = p.get("product_type", "unknown")
            by_type[pt] = by_type.get(pt, 0) + 1
        return {
            "total_purchases": total,
            "daily_spend_usd": round(today_spend, 4),
            "by_type": by_type,
        }
