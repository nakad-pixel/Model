"""
Project Astra - Kie.ai Adapter
Cookie-based fallback video generation on Kie.ai.
"""

import asyncio
import os
from pathlib import Path
from typing import Optional

from playwright.async_api import Page

from src.engine.interaction_handler import InteractionHandler
from src.utils.biometric_sim import BiometricSimulator
from src.utils.logger import logger


class KieAdapter:
    """
    Automates Kie.ai web interface for video generation fallback.
    Uses cookie-based authentication.
    """

    KIE_URL = "https://www.kie.ai"
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
        output_path: str = "media/staging/output_kie.mp4",
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
        """Navigate to Kie.ai and verify login state."""
        try:
            logger.info("Navigating to Kie.ai...")
            await self.page.goto(self.KIE_URL, wait_until="domcontentloaded")
            await self.page.wait_for_load_state("networkidle")

            url = self.page.url
            if "login" in url.lower() or "signin" in url.lower():
                logger.error("Kie.ai redirected to login. Cookies may be expired.")
                return False

            await self.biometrics.sweep_mouse_to_center(self.page)
            logger.info("Kie.ai dashboard loaded.")
            return True
        except Exception as exc:
            logger.error(f"Kie.ai navigation failed: {exc}")
            return False

    async def _inject_prompt(self, prompt: str) -> bool:
        """Type the video prompt into Kie.ai input."""
        try:
            selector = await self.interaction.navigator.find_element(
                "prompt input, text area, or contenteditable for video generation"
            )
            if not selector:
                selector = 'textarea, input[type="text"], div[contenteditable="true"]'

            await self.page.wait_for_selector(selector, timeout=5000)
            await self.page.click(selector)
            await asyncio.sleep(0.3)
            await self.biometrics.type_humanized(self.page, selector, prompt)
            await asyncio.sleep(0.5)

            gen_btn = await self.interaction.navigator.find_element(
                "generate, create, or submit button"
            )
            if gen_btn:
                await self.page.click(gen_btn)
            else:
                await self.page.keyboard.press("Enter")

            logger.info("Kie.ai prompt submitted.")
            return True
        except Exception as exc:
            logger.error(f"Kie.ai prompt injection failed: {exc}")
            return False

    async def _extract_video(self, output_path: str) -> Optional[str]:
        """Poll DOM for generated video and download."""
        logger.info("Polling Kie.ai for generated video...")
        elapsed = 0

        while elapsed < self.GENERATION_TIMEOUT:
            try:
                video_elements = await self.page.query_selector_all("video")
                for video in video_elements:
                    src = await video.evaluate("el => el.src")
                    if src:
                        await self._download_media(src, output_path)
                        if Path(output_path).exists() and Path(output_path).stat().st_size > 10_000:
                            logger.info(f"Kie.ai video extracted: {output_path}")
                            return output_path

                links = await self.page.query_selector_all("a[href*='.mp4'], a[download]")
                for link in links:
                    href = await link.evaluate("el => el.href")
                    if href:
                        await self._download_media(href, output_path)
                        if Path(output_path).exists() and Path(output_path).stat().st_size > 10_000:
                            logger.info(f"Kie.ai video downloaded via link: {output_path}")
                            return output_path

            except Exception as exc:
                logger.debug(f"Kie.ai polling error: {exc}")

            await asyncio.sleep(self.POLL_INTERVAL / 1000)
            elapsed += self.POLL_INTERVAL

        logger.error("Kie.ai extraction timed out.")
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
