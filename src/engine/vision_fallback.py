"""
Project Astra - Vision Fallback
Coordinate-based clicking via GLM-4.7-Vision when DOM parsing fails.
"""

import base64
import json
import os
from typing import Any, Dict, Optional, Tuple

import httpx
from playwright.async_api import Page

from src.utils.logger import logger


class VisionFallback:
    """Uses vision-based reasoning when DOM elements are too obfuscated."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.getenv("GLM_API_KEY")
        self.base_url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

    async def find_coordinates(
        self,
        page: Page,
        objective: str,
    ) -> Optional[Tuple[int, int]]:
        """
        Capture screenshot and ask GLM-4.7-Vision for click coordinates.
        Returns (x, y) or None.
        """
        screenshot = await page.screenshot(type="png", full_page=False)
        screenshot_b64 = base64.b64encode(screenshot).decode("utf-8")

        system_prompt = (
            "You are a visual UI automation assistant. Given a screenshot, "
            "identify the center coordinates of the UI element described by the user. "
            "Respond ONLY with valid JSON: {\"x\": integer, \"y\": integer, \"confidence\": 0-100}. "
            "No markdown, no filler."
        )

        user_content = f"Find the center coordinates of: {objective}"

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_content},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}},
                ],
            },
        ]

        payload = {
            "model": "glm-4v",
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 256,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.base_url,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

            raw = data["choices"][0]["message"]["content"]
            parsed = self._parse_coordinate_response(raw)

            confidence = parsed.get("confidence", 0)
            if confidence >= 70:
                x = parsed.get("x", 0)
                y = parsed.get("y", 0)
                viewport = page.viewport_size
                if viewport:
                    x = max(0, min(x, viewport["width"]))
                    y = max(0, min(y, viewport["height"]))
                logger.info(f"Vision fallback coordinates: ({x}, {y}) confidence={confidence}")
                return (x, y)
            else:
                logger.warning(f"Vision fallback low confidence: {confidence}")
                return None

        except Exception as exc:
            logger.error(f"Vision fallback error: {exc}")
            return None

    async def click_at_coordinates(self, page: Page, x: int, y: int) -> None:
        """Click at specific coordinates on the page."""
        await page.mouse.click(x, y)
        logger.info(f"Clicked at coordinates ({x}, {y})")

    def _parse_coordinate_response(self, raw: str) -> Dict[str, Any]:
        """Parse JSON response from vision model."""
        clean = raw.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        if clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        clean = clean.strip()

        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse vision response: {raw[:200]}")
            return {"x": 0, "y": 0, "confidence": 0}
