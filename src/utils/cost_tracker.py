"""
Project Astra - Cost Tracker
GLM token usage tracking, Nvidia endpoint monitoring, quota alerts.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from src.utils.logger import logger


class CostTracker:
    """
    Tracks API usage costs and quota consumption.
    Alerts at 80% quota usage via telemetry.
    """

    QUOTA_ALERT_THRESHOLD: float = 0.80
    DEFAULT_QUOTA_TOKENS: int = 1_000_000  # Free tier assumption

    def __init__(self, state_path: str = "data/cost_log.json") -> None:
        self.state_path = Path(state_path)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.quota = int(os.getenv("GLM_QUOTA_TOKENS", str(self.DEFAULT_QUOTA_TOKENS)))
        self._load()

    def _load(self) -> None:
        """Load existing cost log or initialize defaults."""
        if self.state_path.exists():
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except (json.JSONDecodeError, OSError):
                self.data = self._default_data()
        else:
            self.data = self._default_data()

    def _default_data(self) -> Dict[str, Any]:
        return {
            "total_tokens_used": 0,
            "total_api_calls": 0,
            "daily_usage": {},
            "last_reset_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "alerts_sent": 0,
            "version": "2026.6.0",
        }

    def _save(self) -> None:
        """Persist cost data atomically."""
        temp = self.state_path.with_suffix(".tmp")
        with open(temp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)
        os.replace(temp, self.state_path)

    def _reset_if_new_day(self) -> None:
        """Reset daily counters if the date has changed."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self.data.get("last_reset_date") != today:
            self.data["last_reset_date"] = today
            self.data["daily_usage"][today] = 0
            logger.info(f"Cost tracker: new day detected, daily counters reset ({today})")
            self._save()

    def record_call(self, tokens_used: int, endpoint: str = "nvidia/glm-4") -> None:
        """
        Record an API call with token usage.
        Args:
            tokens_used: Number of tokens consumed by the call.
            endpoint: The API endpoint hit.
        """
        self._reset_if_new_day()
        self.data["total_tokens_used"] += tokens_used
        self.data["total_api_calls"] += 1

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.data["daily_usage"][today] = self.data["daily_usage"].get(today, 0) + tokens_used

        logger.info(
            f"CostTracker: {tokens_used} tokens used on {endpoint}. "
            f"Total: {self.data['total_tokens_used']:,} | "
            f"Daily: {self.data['daily_usage'][today]:,}"
        )
        self._save()

    def get_usage_ratio(self) -> float:
        """Return current quota usage ratio (0.0 to 1.0+)."""
        return self.data["total_tokens_used"] / max(self.quota, 1)

    def should_alert(self) -> bool:
        """Check if usage has crossed the alert threshold."""
        ratio = self.get_usage_ratio()
        return ratio >= self.QUOTA_ALERT_THRESHOLD

    def check_and_alert(self) -> Optional[str]:
        """
        Check quota and return alert message if threshold crossed.
        Only alerts once per threshold crossing.
        """
        ratio = self.get_usage_ratio()
        if ratio >= self.QUOTA_ALERT_THRESHOLD:
            alert_count = self.data.get("alerts_sent", 0)
            # Simple alert throttling: only alert every 10% beyond threshold
            threshold_crossed = int((ratio - self.QUOTA_ALERT_THRESHOLD) * 10)
            if threshold_crossed > alert_count:
                self.data["alerts_sent"] = threshold_crossed
                self._save()
                msg = (
                    f"🚨 **[ASTRA] Cost Alert:** Quota usage at **{ratio * 100:.1f}%** "
                    f"({self.data['total_tokens_used']:,} / {self.quota:,} tokens)."
                )
                logger.warning(msg)
                return msg
        return None

    def get_summary(self) -> Dict[str, Any]:
        """Return a usage summary dict."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return {
            "total_tokens_used": self.data["total_tokens_used"],
            "total_api_calls": self.data["total_api_calls"],
            "quota": self.quota,
            "usage_ratio": self.get_usage_ratio(),
            "today_usage": self.data["daily_usage"].get(today, 0),
            "last_reset_date": self.data["last_reset_date"],
        }
