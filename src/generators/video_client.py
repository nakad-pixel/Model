"""
Project Astra - Video Client
Unified video generation client with platform adapters and fallback chain.
AI-driven platform selection: Veo 3 (cinematic) > Wan 2.2 (motion) > Kie.ai (fallback).
"""

import asyncio
import os
from pathlib import Path
from typing import Optional

try:
    from patchright.async_api import Page
except Exception:  # pragma: no cover
    from playwright.async_api import Page

from src.engine.interaction_handler import InteractionHandler
from src.generators.kie_adapter import KieAdapter
from src.generators.veo_adapter import VeoAdapter
from src.generators.wan_adapter import WanAdapter
from src.utils.cost_tracker import CostTracker
from src.utils.logger import logger
from src.utils.network_healer import NetworkHealer
from src.utils.telemetry import Telemetry


class VideoClient:
    """
    Unified video generation client.
    Platform router priority:
      1. Veo 3 (cinematic quality)
      2. Wan.video 2.2 (motion control)
      3. Kie.ai (reliable fallback)
    Waits for full video render before returning.
    """

    def __init__(
        self,
        page: Page,
        interaction: Optional[InteractionHandler] = None,
        network_healer: Optional[NetworkHealer] = None,
        telemetry: Optional[Telemetry] = None,
        cost_tracker: Optional[CostTracker] = None,
    ) -> None:
        self.page = page
        self.interaction = interaction or InteractionHandler(page)
        self.network = network_healer or NetworkHealer()
        self.telemetry = telemetry or Telemetry()
        self.cost_tracker = cost_tracker or CostTracker()

        self.veo = VeoAdapter(page, self.interaction)
        self.wan = WanAdapter(page, self.interaction)
        self.kie = KieAdapter(page, self.interaction)

    async def generate_video(
        self,
        prompt: str,
        motion_score: float = 0.0,
        cinematic_score: float = 0.0,
        output_dir: str = "media/staging",
    ) -> Optional[str]:
        """
        Generate video using the platform router with availability checks.
        Waits for full render completion.
        Args:
            prompt: The video generation prompt.
            motion_score: 0.0-1.0, higher means more motion.
            cinematic_score: 0.0-1.0, higher means more cinematic quality.
            output_dir: Directory to save the output video.
        Returns:
            Path to the generated video, or None if all platforms fail.
        """
        platform_order = self._route_platform(motion_score, cinematic_score)
        logger.info(f"Video platform routing: {[p.__class__.__name__ for p in platform_order]}")

        for platform in platform_order:
            platform_name = platform.__class__.__name__
            try:
                healthy = await self._check_platform_health(platform_name)
                if not healthy:
                    logger.warning(f"Skipping {platform_name}: health check failed.")
                    continue

                output_path = Path(output_dir) / f"output_{platform_name.lower().replace('adapter', '')}.mp4"
                result = await platform.generate_video(prompt, str(output_path))

                if result and Path(result).exists():
                    logger.info(f"Video generation succeeded on {platform_name}: {result}")
                    return result

            except Exception as exc:
                logger.error(f"Video generation failed on {platform_name}: {exc}")

        logger.error("All video generation platforms failed.")
        await self.telemetry.send_failure(
            "GENERATING_MEDIA",
            "All video platforms (Veo, Wan, Kie) failed to generate video.",
        )
        return None

    def _route_platform(
        self,
        motion_score: float,
        cinematic_score: float,
    ) -> list:
        """
        Route to platforms based on content analysis scores.
        Priority: Veo 3 > Wan.video > Kie.ai
        - cinematic_score > 0.7 -> Veo 3 first
        - motion_score > 0.7 -> Wan.video first
        - else -> Veo 3 first (default best quality)
        """
        if cinematic_score > 0.7:
            return [self.veo, self.wan, self.kie]
        if motion_score > 0.7:
            return [self.wan, self.veo, self.kie]
        return [self.veo, self.wan, self.kie]

    async def _check_platform_health(self, platform_name: str) -> bool:
        """Check platform availability before video generation."""
        urls = {
            "VeoAdapter": "https://gemini.google.com",
            "WanAdapter": "https://www.wan.video",
            "KieAdapter": "https://www.kie.ai",
        }
        url = urls.get(platform_name)
        if not url:
            return True
        return await self.network.platform_health_check(url)

    async def analyze_content_for_video(self, prompt: str) -> dict:
        """
        Use GLM to analyze prompt and determine if video is appropriate.
        Returns dict with motion_score, cinematic_score, use_video flag.
        """
        import httpx

        api_key = os.getenv("GLM_API_KEY")
        if not api_key:
            logger.warning("GLM_API_KEY not set; defaulting to static image.")
            return {"motion_score": 0.0, "cinematic_score": 0.0, "use_video": False}

        system_prompt = (
            "You are a content analysis engine. Analyze the given image prompt and determine "
            "if it describes motion-heavy content (walking, dancing, exercising) or cinematic content. "
            "Respond ONLY with valid JSON: "
            '{"motion_score": float 0-1, "cinematic_score": float 0-1, "use_video": bool}. '
            "No markdown, no filler."
        )

        payload = {
            "model": "glm-4",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Analyze this prompt: {prompt}"},
            ],
            "temperature": 0.1,
            "max_tokens": 128,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                raw = data["choices"][0]["message"]["content"]
                parsed = self._parse_analysis(raw)
                self.cost_tracker.record_call(
                    tokens_used=data.get("usage", {}).get("total_tokens", 50),
                    endpoint="nvidia/glm-4",
                )
                return parsed
        except Exception as exc:
            logger.error(f"Content analysis failed: {exc}")
            return {"motion_score": 0.0, "cinematic_score": 0.0, "use_video": False}

    def _parse_analysis(self, raw: str) -> dict:
        """Parse JSON analysis response."""
        import json

        clean = raw.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        if clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        clean = clean.strip()

        try:
            parsed = json.loads(clean)
            return {
                "motion_score": float(parsed.get("motion_score", 0.0)),
                "cinematic_score": float(parsed.get("cinematic_score", 0.0)),
                "use_video": bool(parsed.get("use_video", False)),
            }
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error(f"Failed to parse content analysis: {exc}. Raw: {raw[:200]}")
            return {"motion_score": 0.0, "cinematic_score": 0.0, "use_video": False}
