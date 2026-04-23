"""
Project Astra - Social Champ Platform Automation
Additional scheduler support for redundancy.
"""

from typing import Optional

from playwright.async_api import Page

from src.engine.interaction_handler import InteractionHandler
from src.utils.biometric_sim import BiometricSimulator
from src.utils.logger import logger


class SocialChampPlatform:
    """Automates Social Champ dashboard for social media scheduling."""

    SOCIALCHAMP_URL = "https://www.socialchamp.io"

    def __init__(
        self,
        page: Page,
        interaction: Optional[InteractionHandler] = None,
    ) -> None:
        self.page = page
        self.interaction = interaction or InteractionHandler(page)
        self.biometrics = BiometricSimulator()

    async def navigate(self) -> bool:
        """Navigate to Social Champ composer."""
        try:
            logger.info("Navigating to Social Champ...")
            await self.page.goto(self.SOCIALCHAMP_URL, wait_until="domcontentloaded")
            await self.page.wait_for_load_state("networkidle")

            url = self.page.url
            if "login" in url.lower():
                logger.error("Social Champ redirected to login. Cookies may be expired.")
                return False

            await self.biometrics.sweep_mouse_to_center(self.page)
            logger.info("Social Champ dashboard loaded.")
            return True
        except Exception as exc:
            logger.error(f"Social Champ navigation failed: {exc}")
            return False

    async def create_post(self, image_path: str, caption: str) -> bool:
        """Full Social Champ posting pipeline."""
        if not await self.navigate():
            return False

        if not await self.interaction.safe_click("Create Post button"):
            logger.error("Failed to open Social Champ composer.")
            return False

        await self.page.wait_for_timeout(1500)

        # Upload
        try:
            file_input = await self.page.query_selector('input[type="file"]')
            if file_input:
                await file_input.set_input_files(image_path)
                await self.page.wait_for_timeout(3000)
        except Exception as exc:
            logger.error(f"Social Champ upload failed: {exc}")
            return False

        # Caption
        if not await self.interaction.safe_fill("caption textarea", caption):
            logger.error("Caption injection failed on Social Champ.")
            return False

        await self.page.wait_for_timeout(1000)

        # Schedule
        if not await self.interaction.safe_click("Schedule or Post button"):
            logger.error("Failed to schedule post on Social Champ.")
            return False

        logger.info("Social Champ post scheduled successfully.")
        return True
