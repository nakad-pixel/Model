"""
Project Astra - Clipchamp Platform Automation
Automates video posting to Clipchamp scheduler.
"""

from typing import Optional

from playwright.async_api import Page

from src.engine.interaction_handler import InteractionHandler
from src.utils.biometric_sim import BiometricSimulator
from src.utils.logger import logger


class ClipchampPlatform:
    """Automates Clipchamp for video posting and scheduling."""

    CLIPCHAMP_URL = "https://clipchamp.com"
    UPLOAD_TIMEOUT = 60_000

    def __init__(
        self,
        page: Page,
        interaction: Optional[InteractionHandler] = None,
    ) -> None:
        self.page = page
        self.interaction = interaction or InteractionHandler(page)
        self.biometrics = BiometricSimulator()

    async def navigate(self) -> bool:
        """Navigate to Clipchamp and verify login state."""
        try:
            logger.info("Navigating to Clipchamp...")
            await self.page.goto(self.CLIPCHAMP_URL, wait_until="domcontentloaded")
            await self.page.wait_for_load_state("networkidle")

            url = self.page.url
            if "login" in url.lower() or "signin" in url.lower():
                logger.error("Clipchamp redirected to login. Cookies may be expired.")
                return False

            await self.biometrics.sweep_mouse_to_center(self.page)
            logger.info("Clipchamp dashboard loaded.")
            return True
        except Exception as exc:
            logger.error(f"Clipchamp navigation failed: {exc}")
            return False

    async def create_post(self, video_path: str, caption: str) -> bool:
        """
        Full Clipchamp posting pipeline for video content.
        Returns True on success.
        """
        if not await self.navigate():
            return False

        # Step 1: Click Create/Upload
        if not await self.interaction.safe_click(
            "Create, Upload, or New Project button",
            fallback_selector='button:has-text("Create"), button:has-text("Upload")',
        ):
            logger.error("Failed to open Clipchamp composer.")
            return False

        await self.page.wait_for_timeout(2000)

        # Step 2: Upload video
        if not await self._upload_video(video_path):
            logger.error("Video upload failed on Clipchamp.")
            return False

        # Step 3: Inject caption / title
        if not await self.interaction.safe_fill(
            "caption, title, or description field",
            caption,
            fallback_selector='textarea, input[placeholder*="title"], input[placeholder*="description"]',
        ):
            logger.error("Caption injection failed on Clipchamp.")
            return False

        await self.page.wait_for_timeout(1000)

        # Step 4: Save / Export / Schedule
        if not await self.interaction.safe_click(
            "Save, Export, or Schedule button",
            fallback_selector='button:has-text("Save"), button:has-text("Export")',
        ):
            logger.error("Failed to save post on Clipchamp.")
            return False

        logger.info("Clipchamp video post created successfully.")
        return True

    async def _upload_video(self, video_path: str) -> bool:
        """Upload video file to Clipchamp."""
        try:
            file_input = await self.page.query_selector('input[type="file"]')
            if file_input:
                await file_input.set_input_files(video_path)
                logger.info("Video uploaded to Clipchamp via file input.")
                await self.page.wait_for_timeout(5000)
                return True

            return await self.interaction.safe_upload(
                'input[type="file"]',
                video_path,
            )
        except Exception as exc:
            logger.error(f"Clipchamp video upload error: {exc}")
            return False
