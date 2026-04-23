"""
Project Astra - Metricool Platform Automation
Automates post creation and scheduling on Metricool dashboard.
"""

from typing import Optional

from playwright.async_api import Page

from src.constants import FALLBACK_SELECTORS
from src.engine.interaction_handler import InteractionHandler
from src.utils.biometric_sim import BiometricSimulator
from src.utils.logger import logger


class MetricoolPlatform:
    """Automates Metricool planner for social media scheduling."""

    METRICOOL_URL = "https://app.metricool.com"
    UPLOAD_TIMEOUT = 30_000

    def __init__(
        self,
        page: Page,
        interaction: Optional[InteractionHandler] = None,
    ) -> None:
        self.page = page
        self.interaction = interaction or InteractionHandler(page)
        self.biometrics = BiometricSimulator()

    async def navigate(self) -> bool:
        """Navigate to Metricool and verify login state."""
        try:
            logger.info("Navigating to Metricool...")
            await self.page.goto(self.METRICOOL_URL, wait_until="domcontentloaded")
            await self.page.wait_for_load_state("networkidle")

            url = self.page.url
            if "login" in url.lower() or "signin" in url.lower():
                logger.error("Metricool redirected to login. Cookies may be expired.")
                return False

            await self.biometrics.sweep_mouse_to_center(self.page)
            logger.info("Metricool dashboard loaded.")
            return True
        except Exception as exc:
            logger.error(f"Metricool navigation failed: {exc}")
            return False

    async def create_post(self, image_path: str, caption: str) -> bool:
        """
        Full Metricool posting pipeline.
        Returns True on success.
        """
        if not await self.navigate():
            return False

        # Step 1: Click Create/Compose
        if not await self.interaction.safe_click(
            "Create new post or compose button",
            fallback_selector=FALLBACK_SELECTORS.get("metricool_compose_button"),
        ):
            logger.error("Failed to open Metricool composer.")
            return False

        await self.page.wait_for_timeout(1500)

        # Step 2: Upload image
        if not await self._upload_image(image_path):
            logger.error("Image upload failed on Metricool.")
            return False

        # Step 3: Inject caption
        if not await self.interaction.safe_fill(
            "caption text area",
            caption,
            fallback_selector=FALLBACK_SELECTORS.get("metricool_caption_box"),
        ):
            logger.error("Caption injection failed on Metricool.")
            return False

        await self.page.wait_for_timeout(1000)

        # Step 4: Schedule
        if not await self.interaction.safe_click(
            "Schedule or Save button",
            fallback_selector=FALLBACK_SELECTORS.get("metricool_schedule_button"),
        ):
            logger.error("Failed to schedule post on Metricool.")
            return False

        logger.info("Metricool post scheduled successfully.")
        return True

    async def _upload_image(self, image_path: str) -> bool:
        """Upload image file to Metricool composer."""
        try:
            file_input = await self.page.query_selector(
                FALLBACK_SELECTORS.get("metricool_file_input", 'input[type="file"]')
            )
            if file_input:
                await file_input.set_input_files(image_path)
                logger.info("Image uploaded to Metricool via file input.")
                await self.page.wait_for_timeout(3000)
                return True

            return await self.interaction.safe_upload(
                FALLBACK_SELECTORS.get("metricool_file_input", 'input[type="file"]'),
                image_path,
            )
        except Exception as exc:
            logger.error(f"Metricool image upload error: {exc}")
            return False
