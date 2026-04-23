"""
Project Astra - Buffer Platform Automation
Automates post creation and scheduling on Buffer dashboard.
"""

from typing import Optional

from playwright.async_api import Page

from src.constants import FALLBACK_SELECTORS
from src.engine.interaction_handler import InteractionHandler
from src.utils.biometric_sim import BiometricSimulator
from src.utils.logger import logger


class BufferPlatform:
    """Automates Buffer publish dashboard for social media scheduling."""

    BUFFER_URL = "https://publish.buffer.com"
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
        """Navigate to Buffer and verify login state."""
        try:
            logger.info("Navigating to Buffer...")
            await self.page.goto(self.BUFFER_URL, wait_until="domcontentloaded")
            await self.page.wait_for_load_state("networkidle")

            # Check for redirect to login (cookie expired)
            url = self.page.url
            if "login" in url.lower() or "signin" in url.lower():
                logger.error("Buffer redirected to login. Cookies may be expired.")
                return False

            await self.biometrics.sweep_mouse_to_center(self.page)
            logger.info("Buffer dashboard loaded.")
            return True
        except Exception as exc:
            logger.error(f"Buffer navigation failed: {exc}")
            return False

    async def create_post(self, image_path: str, caption: str) -> bool:
        """
        Full Buffer posting pipeline: compose, upload, caption, schedule.
        Returns True on success.
        """
        if not await self.navigate():
            return False

        # Step 1: Click "Create Post" / "Compose"
        if not await self.interaction.safe_click(
            "Create Post button or Compose button",
            fallback_selector=FALLBACK_SELECTORS.get("buffer_compose_button"),
        ):
            logger.error("Failed to open Buffer composer.")
            return False

        await self.page.wait_for_timeout(1500)

        # Step 2: Upload image
        if not await self._upload_image(image_path):
            logger.error("Image upload failed on Buffer.")
            return False

        # Step 3: Inject caption
        if not await self.interaction.safe_fill(
            "caption text area or contenteditable field",
            caption,
            fallback_selector=FALLBACK_SELECTORS.get("buffer_caption_box"),
        ):
            logger.error("Caption injection failed on Buffer.")
            return False

        await self.page.wait_for_timeout(1000)

        # Step 4: Schedule / Add to Queue
        if not await self.interaction.safe_click(
            "Add to Queue or Schedule button",
            fallback_selector=FALLBACK_SELECTORS.get("buffer_schedule_button"),
        ):
            logger.error("Failed to schedule post on Buffer.")
            return False

        # Step 5: Verify success toast
        success = await self._verify_success()
        if success:
            logger.info("Buffer post scheduled successfully.")
        else:
            logger.warning("Buffer scheduling may have succeeded but toast not detected.")

        return True

    async def _upload_image(self, image_path: str) -> bool:
        """Upload image file to Buffer composer."""
        try:
            # Try direct file input injection first
            file_input = await self.page.query_selector(
                FALLBACK_SELECTORS.get("buffer_file_input", 'input[type="file"]')
            )
            if file_input:
                await file_input.set_input_files(image_path)
                logger.info("Image uploaded via file input.")
                await self.page.wait_for_timeout(3000)
                return True

            # Fallback: try filechooser event
            return await self.interaction.safe_upload(
                FALLBACK_SELECTORS.get("buffer_file_input", 'input[type="file"]'),
                image_path,
            )
        except Exception as exc:
            logger.error(f"Buffer image upload error: {exc}")
            return False

    async def _verify_success(self) -> bool:
        """Poll for success toast notification."""
        try:
            # Common success indicators
            indicators = [
                "text='added to queue'",
                "text='Post scheduled'",
                "text='Success'",
                ".toast",
                "[role='alert']",
            ]
            for indicator in indicators:
                try:
                    await self.page.wait_for_selector(indicator, timeout=5000)
                    return True
                except Exception:
                    continue
            return False
        except Exception as exc:
            logger.debug(f"Success verification error: {exc}")
            return False
