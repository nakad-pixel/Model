"""
Project Astra - Interaction Handler
Wrapper for Playwright actions with biometric noise and safety checks.
"""

from typing import Optional

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from src.engine.heuristic_navigator import HeuristicNavigator
from src.engine.vision_fallback import VisionFallback
from src.utils.biometric_sim import BiometricSimulator
from src.utils.logger import logger


class InteractionHandler:
    """Safe wrapper around Playwright actions with fallback strategies."""

    def __init__(
        self,
        page: Page,
        api_key: Optional[str] = None,
        use_biometrics: bool = True,
    ) -> None:
        self.page = page
        self.navigator = HeuristicNavigator(page, api_key)
        self.vision = VisionFallback(api_key)
        self.biometrics = BiometricSimulator()
        self.use_biometrics = use_biometrics

    async def safe_click(self, objective: str, fallback_selector: Optional[str] = None) -> bool:
        """
        Attempt to click an element identified by AI Chrome heuristic.
        Falls back to vision coordinates, then to static selector.
        """
        # Strategy 1: Heuristic navigator
        selector = await self.navigator.find_element(objective)
        if selector:
            return await self._click_selector(selector)

        # Strategy 2: Vision fallback
        logger.warning(f"Heuristic failed for '{objective}'. Trying vision fallback...")
        coords = await self.vision.find_coordinates(self.page, objective)
        if coords:
            x, y = coords
            if self.use_biometrics:
                await self.biometrics.mouse_move_humanized(self.page, x, y)
            await self.vision.click_at_coordinates(self.page, x, y)
            return True

        # Strategy 3: Static fallback selector
        if fallback_selector:
            logger.warning(f"Vision fallback failed. Using static selector: {fallback_selector}")
            return await self._click_selector(fallback_selector)

        logger.error(f"All click strategies failed for objective: {objective}")
        return False

    async def safe_fill(self, objective: str, text: str, fallback_selector: Optional[str] = None) -> bool:
        """
        Fill a text field identified by AI Chrome heuristic with biometric typing.
        """
        selector = await self.navigator.find_element(objective)
        if not selector and fallback_selector:
            selector = fallback_selector

        if not selector:
            logger.error(f"Could not find fill target for: {objective}")
            return False

        try:
            await self.page.wait_for_selector(selector, timeout=5000)
            element = await self.page.query_selector(selector)
            if not element:
                return False

            await element.click()
            await self.page.wait_for_timeout(200)

            if self.use_biometrics:
                await self.biometrics.type_humanized(self.page, selector, text)
            else:
                await element.fill(text)

            logger.info(f"Filled text into {selector}")
            return True
        except PlaywrightTimeoutError:
            logger.error(f"Timeout waiting for fill target: {selector}")
            return False
        except Exception as exc:
            logger.error(f"Fill error on {selector}: {exc}")
            return False

    async def safe_wait(self, objective: str, timeout: int = 30000) -> bool:
        """Wait for an element to appear using heuristic detection."""
        selector = await self.navigator.find_element(objective, use_vision=False)
        if not selector:
            return False
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            return True
        except PlaywrightTimeoutError:
            return False

    async def safe_upload(self, fallback_selector: str, file_path: str) -> bool:
        """Upload a file using static selector (file inputs are usually reliable)."""
        try:
            input_element = await self.page.query_selector(fallback_selector)
            if input_element:
                await input_element.set_input_files(file_path)
                logger.info(f"Uploaded file: {file_path}")
                return True
            # Try with filechooser event
            async with self.page.expect_file_chooser() as fc_info:
                # Trigger file chooser via heuristic or fallback
                trigger = await self.navigator.find_element("upload button or file input trigger")
                if trigger:
                    await self.page.click(trigger)
                else:
                    await self.page.click(fallback_selector)
                file_chooser = await fc_info.value
                await file_chooser.set_files(file_path)
            logger.info(f"Uploaded file via filechooser: {file_path}")
            return True
        except Exception as exc:
            logger.error(f"Upload failed: {exc}")
            return False

    async def _click_selector(self, selector: str) -> bool:
        """Internal: click a resolved selector with optional biometric movement."""
        try:
            element = await self.page.query_selector(selector)
            if not element:
                return False

            if self.use_biometrics:
                box = await element.bounding_box()
                if box:
                    center_x = int(box["x"] + box["width"] / 2)
                    center_y = int(box["y"] + box["height"] / 2)
                    await self.biometrics.mouse_move_humanized(self.page, center_x, center_y)

            await element.click()
            logger.info(f"Clicked selector: {selector}")
            return True
        except Exception as exc:
            logger.error(f"Click failed on {selector}: {exc}")
            return False
