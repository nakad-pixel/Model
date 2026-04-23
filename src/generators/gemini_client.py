"""
Project Astra - Gemini Client
Specialized automation for the Gemini web interface image generation.
"""

import asyncio
import os
from pathlib import Path
from typing import Optional

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from src.constants import FALLBACK_SELECTORS
from src.engine.interaction_handler import InteractionHandler
from src.utils.biometric_sim import BiometricSimulator
from src.utils.logger import logger


class GeminiClient:
    """Automates Gemini web interface for AI image generation."""

    GEMINI_URL = "https://gemini.google.com/app"
    GENERATION_TIMEOUT = 60_000  # 60 seconds
    POLL_INTERVAL = 2_000       # 2 seconds

    def __init__(
        self,
        page: Page,
        interaction: Optional[InteractionHandler] = None,
    ) -> None:
        self.page = page
        self.interaction = interaction or InteractionHandler(page)
        self.biometrics = BiometricSimulator()

    async def navigate(self) -> bool:
        """Navigate to Gemini and wait for network idle."""
        try:
            logger.info("Navigating to Gemini...")
            await self.page.goto(self.GEMINI_URL, wait_until="domcontentloaded")
            await self.page.wait_for_load_state("networkidle")
            await self.biometrics.sweep_mouse_to_center(self.page)
            logger.info("Gemini page loaded.")
            return True
        except Exception as exc:
            logger.error(f"Gemini navigation failed: {exc}")
            return False

    async def inject_prompt(self, prompt: str) -> bool:
        """Type the image generation prompt into Gemini's input box."""
        try:
            # Try heuristic first, then fallback
            selector = await self.interaction.navigator.find_element(
                "text input field for entering prompts"
            )
            if not selector:
                selector = FALLBACK_SELECTORS.get("gemini_textbox")

            if not selector:
                logger.error("Could not find Gemini input selector.")
                return False

            await self.page.wait_for_selector(selector, timeout=5000)
            await self.page.click(selector)
            await asyncio.sleep(0.3)

            # Type with biometric delays
            await self.biometrics.type_humanized(self.page, selector, prompt)
            await asyncio.sleep(0.5)

            # Submit prompt
            await self.page.keyboard.press("Enter")
            logger.info("Prompt submitted to Gemini.")
            return True
        except Exception as exc:
            logger.error(f"Prompt injection failed: {exc}")
            return False

    async def extract_image(self, output_path: str = "media/staging/output_raw.png") -> Optional[str]:
        """
        Poll DOM for generated image and download it.
        Returns path to saved image or None.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info("Polling for generated image...")
        elapsed = 0

        while elapsed < self.GENERATION_TIMEOUT:
            try:
                # Look for image elements that appear after generation
                img_elements = await self.page.query_selector_all("img")
                for img in img_elements:
                    src = await img.evaluate("el => el.src")
                    alt = await img.evaluate("el => el.alt || ''")

                    if src and ("generat" in alt.lower() or "blob:" in src or src.startswith("http")):
                        # Download the image
                        if src.startswith("blob:"):
                            # Extract via page evaluation for blob URLs
                            image_data = await self.page.evaluate(
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
                            if image_data and isinstance(image_data, str):
                                import base64
                                b64_data = image_data.split(",")[1]
                                image_bytes = base64.b64decode(b64_data)
                                with open(output_path, "wb") as f:
                                    f.write(image_bytes)
                        else:
                            # Direct HTTP download via Playwright request
                            context = self.page.context
                            response = await context.request.get(src)
                            if response.ok:
                                image_bytes = await response.body()
                                with open(output_path, "wb") as f:
                                    f.write(image_bytes)

                        if output_path.exists() and output_path.stat().st_size > 1000:
                            logger.info(f"Image extracted and saved: {output_path}")
                            return str(output_path)

            except Exception as exc:
                logger.debug(f"Polling iteration error: {exc}")

            await asyncio.sleep(self.POLL_INTERVAL / 1000)
            elapsed += self.POLL_INTERVAL

        logger.error("Image extraction timed out.")
        return None

    async def generate_image(
        self,
        prompt: str,
        output_path: str = "media/staging/output_raw.png",
    ) -> Optional[str]:
        """
        Full pipeline: navigate, inject prompt, wait for generation, extract image.
        Returns path to saved image or None.
        """
        if not await self.navigate():
            return None

        if not await self.inject_prompt(prompt):
            return None

        # Wait for generation to start
        await asyncio.sleep(3)

        return await self.extract_image(output_path)
