"""
Project Astra - Cookie Manager
Per-persona cookie health management with manual paste + auto-refresh support.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.utils.logger import logger


@dataclass
class CookieHealth:
    platform: str
    healthy: bool
    score: float  # 0.0 - 1.0
    last_checked: Optional[str] = None


class CookieManager:
    """
    Loads per-persona cookies from environment variables,
    tracks cookie health, and alerts when health drops below threshold.
    """

    HEALTH_ALERT_THRESHOLD: float = 0.50

    def __init__(self, persona_id: str = "astra") -> None:
        self.persona_id = persona_id
        self.cookies_dir = Path(f"data/{persona_id}/cookies")
        self.cookies_dir.mkdir(parents=True, exist_ok=True)
        self.health_log: Dict[str, CookieHealth] = {}

    def get_env_key(self, platform: str) -> str:
        """Build the environment variable key for a platform's cookies."""
        return f"{platform.upper()}_COOKIES_{self.persona_id.upper()}"

    def load_cookies(self, platform: str) -> Optional[str]:
        """
        Load raw cookie JSON for a platform from environment.
        Falls back to cached file if env var is not set.
        """
        env_key = self.get_env_key(platform)
        raw = os.getenv(env_key)
        if raw:
            # Cache to file for local recovery
            cache_path = self.cookies_dir / f"{platform}_cookies.json"
            try:
                with open(cache_path, "w", encoding="utf-8") as f:
                    f.write(raw)
            except OSError as exc:
                logger.debug(f"Cookie cache write failed: {exc}")
            return raw

        # Fallback to cached file
        cache_path = self.cookies_dir / f"{platform}_cookies.json"
        if cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    return f.read()
            except OSError as exc:
                logger.debug(f"Cookie cache read failed: {exc}")

        logger.warning(f"No cookies found for {platform}/{self.persona_id} (env: {env_key})")
        return None

    def parse_cookies(self, raw_json: str) -> List[Dict[str, Any]]:
        """Parse and validate cookie JSON."""
        try:
            data = json.loads(raw_json)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "cookies" in data:
                return data["cookies"]
            return []
        except json.JSONDecodeError as exc:
            logger.error(f"Cookie JSON parse error: {exc}")
            return []

    def all_platforms(self) -> List[str]:
        """Return list of supported platform names."""
        return ["gemini", "wan", "kie", "buffer", "metricool"]

    def health_check(self, platform: str) -> CookieHealth:
        """
        Perform a basic health check on cookies for a platform.
        Returns CookieHealth with a score based on cookie presence and validity.
        """
        raw = self.load_cookies(platform)
        if not raw:
            health = CookieHealth(platform=platform, healthy=False, score=0.0)
            self.health_log[platform] = health
            return health

        cookies = self.parse_cookies(raw)
        score = min(1.0, len(cookies) / 5.0)  # Rough heuristic: 5+ cookies = full score
        healthy = score >= self.HEALTH_ALERT_THRESHOLD

        from datetime import datetime, timezone

        health = CookieHealth(
            platform=platform,
            healthy=healthy,
            score=score,
            last_checked=datetime.now(timezone.utc).isoformat(),
        )
        self.health_log[platform] = health
        return health

    def full_health_report(self) -> Dict[str, Any]:
        """Run health checks across all platforms and return summary."""
        report: Dict[str, Any] = {"persona_id": self.persona_id, "platforms": {}}
        any_unhealthy = False
        for platform in self.all_platforms():
            health = self.health_check(platform)
            report["platforms"][platform] = {
                "healthy": health.healthy,
                "score": round(health.score, 2),
                "last_checked": health.last_checked,
            }
            if not health.healthy:
                any_unhealthy = True
        report["overall_healthy"] = not any_unhealthy
        return report

    def should_alert(self) -> List[str]:
        """Return list of platforms with cookie health below threshold."""
        alerts: List[str] = []
        for platform in self.all_platforms():
            health = self.health_check(platform)
            if not health.healthy:
                alerts.append(platform)
        return alerts
