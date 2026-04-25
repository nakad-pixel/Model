"""
Project Astra - Wan.video Adapter (2.2)
Cookie-based video generation on Wan.video.
"""

import asyncio
import os
from pathlib import Path
from typing import Optional

from playwright.async_api import Page

from src.engine.interaction_handler import InteractionHandler
from src.utils.biometric_sim import BiometricSimulator
from src.utils.logger import logger


class WanAdapter:
    """
    Automates Wan.video (2.2) web interface for video generation.
    Uses cookie-based authentication like Gemini.
    """

    WAN_URL = "https://www.wan.video"
    GENERATION_TIMEOUT = 300_000  # 5 minutes
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
        output_path: str = "media/staging/output_wan.mp4",
    ) -> Optional[str]:
        """
        Full pipeline: navigate, inject prompt, poll and download video.
        Returns path to saved video or None.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if not await self._navigate():
            return None
        if not await self._inject_prompt(prompt):
            return None

        await asyncio.sleep(5)
        return await self._extract_video(str(output_path))

    async def _navigate(self) -> bool:
        """Navigate to Wan.video and verify login."""
        try:
            logger.info("Navigating to Wan.video...")
            await self.page.goto(self.WAN_URL, wait_until="domcontentloaded")
            await self.page.wait_for_load_state("networkidle")

            url = self.page.url
            if "login" in url.lower() or "signin" in url.lower():
                logger.error("Wan.video redirected to login. Cookies may be expired.")
                return False

            await self.biometrics.sweep_mouse_to_center(self.page)
            logger.info("Wan.video dashboard loaded.")
            return True
        except Exception as exc:
            logger.error(f"Wan.video navigation failed: {exc}")
            return False

    async def _inject_prompt(self, prompt: str) -> bool:
        """Type the video prompt into Wan.video input."""
        try:
            selector = await self.interaction.navigator.find_element(
                "prompt input or text area for video description"
            )
            if not selector:
                # Fallback: common selectors for Wan.video
                selector = 'textarea[placeholder*="prompt"], div[contenteditable="true"], input[type="text"]'

            await self.page.wait_for_selector(selector, timeout=5000)
            await self.page.click(selector)
            await asyncio.sleep(0.3)
            await self.biometrics.type_humanized(self.page, selector, prompt)
            await asyncio.sleep(0.5)

            # Find generate button
            gen_btn = await self.interaction.navigator.find_element(
                "generate or create video button"
            )
            if gen_btn:
                await self.page.click(gen_btn)
            else:
                await self.page.keyboard.press("Enter")

            logger.info("Wan.video prompt submitted.")
            return True
        except Exception as exc:
            logger.error(f"Wan.video prompt injection failed: {exc}")
            return False

    async def _extract_video(self, output_path: str) -> Optional[str]:
        """Poll DOM for generated video and download."""
        logger.info("Polling Wan.video for generated video...")
        elapsed = 0

        while elapsed < self.GENERATION_TIMEOUT:
            try:
                # Wan.video may use video tags or direct download links
                video_elements = await self.page.query_selector_all("video")
                for video in video_elements:
                    src = await video.evaluate("el => el.src")
                    if src:
                        await self._download_media(src, output_path)
                        if Path(output_path).exists() and Path(output_path).stat().st_size > 10_000:
                            logger.info(f"Wan.video extracted: {output_path}")
                            return output_path

                # Check for download links
                links = await self.page.query_selector_all("a[href*='.mp4'], a[download]")
                for link in links:
                    href = await link.evaluate("el => el.href")
                    if href:
                        await self._download_media(href, output_path)
                        if Path(output_path).exists() and Path(output_path).stat().st_size > 10_000:
                            logger.info(f"Wan.video downloaded via link: {output_path}")
                            return output_path

            except Exception as exc:
                logger.debug(f"Wan.video polling error: {exc}")

            await asyncio.sleep(self.POLL_INTERVAL / 1000)
            elapsed += self.POLL_INTERVAL

        logger.error("Wan.video extraction timed out.")
        return None

    async def _download_media(self, src: str, output_path: str) -> None:
        """Download media from src URL."""
        if src.startswith("blob:"):
            media_data = await self.page.evaluate(
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
            if media_data and isinstance(media_data, str):
                import base64
                b64_data = media_data.split(",")[1]
                with open(output_path, "wb") as f:
                    f.write(base64.b64decode(b64_data))
        else:
            context = self.page.context
            response = await context.request.get(src)
            if response.ok:
                with open(output_path, "wb") as f:
                    f.write(await response.body())
