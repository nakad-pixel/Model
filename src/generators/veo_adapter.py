"""
Project Astra - Veo Adapter
Gemini Veo 3 video generation using the same session cookies as Gemini image gen.
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
from src.utils.biometric_sim import BiometricSimulator
from src.utils.logger import logger


class VeoAdapter:
    """
    Automates Gemini Veo 3 video generation via the Gemini web interface.
    Reuses the same cookie-based session as GeminiClient.
    """

    VEO_URL = "https://gemini.google.com/app"
    GENERATION_TIMEOUT = 180_000  # 3 minutes for video
    POLL_INTERVAL = 5_000         # 5 seconds

    def __init__(
        self,
        page: Page,
        interaction: Optional[InteractionHandler] = None,
    ) -> None:
        self.page = page
        self.interaction = interaction or InteractionHandler(page)
        self.biometrics = BiometricSimulator()

    async def generate_video(
        self,
        prompt: str,
        output_path: str = "media/staging/output_video.mp4",
    ) -> Optional[str]:
        """
        Full pipeline: navigate to Gemini, request video generation, poll and download.
        Returns path to saved video or None.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if not await self._navigate():
            return None
        if not await self._inject_video_prompt(prompt):
            return None

        await asyncio.sleep(5)
        return await self._extract_video(str(output_path))

    async def _navigate(self) -> bool:
        """Navigate to Gemini app."""
        try:
            logger.info("Navigating to Gemini for Veo 3 video...")
            await self.page.goto(self.VEO_URL, wait_until="domcontentloaded")
            await self.page.wait_for_load_state("networkidle")
            await self.biometrics.sweep_mouse_to_center(self.page)
            logger.info("Gemini page loaded for Veo.")
            return True
        except Exception as exc:
            logger.error(f"Veo navigation failed: {exc}")
            return False

    async def _inject_video_prompt(self, prompt: str) -> bool:
        """Type a video-generation prompt into Gemini."""
        try:
            # Find input
            selector = await self.interaction.navigator.find_element(
                "text input field for entering prompts"
            )
            if not selector:
                from src.constants import FALLBACK_SELECTORS
                selector = FALLBACK_SELECTORS.get("gemini_textbox")

            if not selector:
                logger.error("Could not find Gemini input selector for Veo.")
                return False

            await self.page.wait_for_selector(selector, timeout=5000)
            await self.page.click(selector)
            await asyncio.sleep(0.3)

            # Add video directive
            video_prompt = f"Generate a short cinematic video: {prompt}"
            await self.biometrics.type_humanized(self.page, selector, video_prompt)
            await asyncio.sleep(0.5)
            await self.page.keyboard.press("Enter")
            logger.info("Veo video prompt submitted.")
            return True
        except Exception as exc:
            logger.error(f"Veo prompt injection failed: {exc}")
            return False

    async def _extract_video(self, output_path: str) -> Optional[str]:
        """Poll DOM for generated video and download it."""
        logger.info("Polling for generated video...")
        elapsed = 0

        while elapsed < self.GENERATION_TIMEOUT:
            try:
                video_elements = await self.page.query_selector_all("video")
                for video in video_elements:
                    src = await video.evaluate("el => el.src")
                    if src and (src.startswith("http") or src.startswith("blob:")):
                        if src.startswith("blob:"):
                            video_data = await self.page.evaluate(
                                """
                                async (src) => {
                                    const response = await fetch(src);
                                    const blob = await response.blob();
                                    return new Promise((resolve) => {
                                        const reader = new FileReader();
                                        reader.onloadend = () => resolve(reader.result);
                                        reader.readAsDataURL(blob);
                                    });
                                }
                                """,
                                src,
                            )
                            if video_data and isinstance(video_data, str):
                                import base64
                                b64_data = video_data.split(",")[1]
                                video_bytes = base64.b64decode(b64_data)
                                with open(output_path, "wb") as f:
                                    f.write(video_bytes)
                        else:
                            context = self.page.context
                            response = await context.request.get(src)
                            if response.ok:
                                video_bytes = await response.body()
                                with open(output_path, "wb") as f:
                                    f.write(video_bytes)

                        if Path(output_path).exists() and Path(output_path).stat().st_size > 10_000:
                            logger.info(f"Video extracted and saved: {output_path}")
                            return output_path

            except Exception as exc:
                logger.debug(f"Video polling iteration error: {exc}")

            await asyncio.sleep(self.POLL_INTERVAL / 1000)
            elapsed += self.POLL_INTERVAL

        logger.error("Video extraction timed out.")
        return None
