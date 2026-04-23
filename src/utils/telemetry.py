"""
Project Astra - Telemetry Module
Discord webhook integration for human-in-the-loop alerts.
"""

import base64
import os
from pathlib import Path
from typing import Optional

import httpx

from src.utils.logger import logger


class Telemetry:
    """Real-time monitoring and alerting via Discord webhooks."""

    def __init__(self, webhook_url: Optional[str] = None) -> None:
        self.webhook_url = webhook_url or os.getenv("DISCORD_WEBHOOK")
        if not self.webhook_url:
            logger.warning("DISCORD_WEBHOOK not set. Telemetry alerts disabled.")

    async def send_success(self, context: str, image_path: Optional[str] = None) -> bool:
        """Send a success notification with optional image attachment."""
        if not self.webhook_url:
            return False

        payload = {
            "content": f"✅ **[ASTRA] Workflow Complete.** Post added to queue successfully.",
            "embeds": [
                {
                    "title": "Astra Agent - Success",
                    "color": 0x00FF00,
                    "fields": [
                        {"name": "Context", "value": context, "inline": False},
                        {"name": "Status", "value": "Image Validation: PASS", "inline": True},
                    ],
                    "timestamp": self._now_iso(),
                }
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if image_path and Path(image_path).exists():
                    with open(image_path, "rb") as f:
                        files = {"file": ("astra_output.png", f, "image/png")}
                        response = await client.post(
                            self.webhook_url,
                            data={"payload_json": str(payload).replace("'", '"')},
                            files=files,
                        )
                else:
                    response = await client.post(self.webhook_url, json=payload)

            if response.status_code == 204:
                logger.info("Telemetry: Success notification sent.")
                return True
            else:
                logger.error(f"Telemetry failed: HTTP {response.status_code}")
                return False
        except Exception as exc:
            logger.error(f"Telemetry exception: {exc}")
            return False

    async def send_failure(
        self,
        phase: str,
        error_message: str,
        screenshot_path: Optional[str] = None,
    ) -> bool:
        """Send a failure alert with optional crash screenshot."""
        if not self.webhook_url:
            return False

        embed = {
            "title": "🚨 Astra Agent - CRITICAL FAILURE",
            "color": 0xFF0000,
            "fields": [
                {"name": "Phase", "value": phase, "inline": True},
                {"name": "Error", "value": f"```{error_message[:1000]}```", "inline": False},
                {"name": "Action Required", "value": "Manual Codespace intervention required.", "inline": False},
            ],
            "timestamp": self._now_iso(),
        }

        if screenshot_path and Path(screenshot_path).exists():
            with open(screenshot_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            embed["image"] = {"url": f"data:image/png;base64,{b64}"}

        payload = {
            "content": f"🚨 **[ASTRA] CRITICAL:** Workflow FAILED at Phase **{phase}**.",
            "embeds": [embed],
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.webhook_url, json=payload)

            if response.status_code == 204:
                logger.info("Telemetry: Failure notification sent.")
                return True
            else:
                logger.error(f"Telemetry failure post failed: HTTP {response.status_code}")
                return False
        except Exception as exc:
            logger.error(f"Telemetry exception: {exc}")
            return False

    async def send_cookie_expired(self, platform: str) -> bool:
        """Alert when session cookies have expired."""
        if not self.webhook_url:
            return False

        payload = {
            "content": f"⚠️ **[ASTRA] Cookie Expired** on platform: **{platform}**.",
            "embeds": [
                {
                    "title": "Authentication Failure",
                    "color": 0xFFA500,
                    "fields": [
                        {"name": "Platform", "value": platform, "inline": True},
                        {"name": "Action", "value": "Refresh cookies from local browser session.", "inline": False},
                    ],
                }
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.webhook_url, json=payload)
            return response.status_code == 204
        except Exception as exc:
            logger.error(f"Telemetry cookie alert exception: {exc}")
            return False

    @staticmethod
    def _now_iso() -> str:
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat()
