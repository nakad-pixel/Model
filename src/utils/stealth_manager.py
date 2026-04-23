"""
Project Astra - Stealth Manager (Layers 2 & 3)
Configures rebrowser-playwright with stealth plugins and fingerprint evasion.
"""

import json
import os
import random
from typing import Any, Dict, List, Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from src.constants import (
    BROWSER_LAUNCH_ARGS,
    DEVICE_SCALE_FACTOR,
    GEOLOCATION_INDIA,
    MOBILE_USER_AGENTS,
    VIEWPORT_CONFIG,
)
from src.utils.logger import logger


class StealthManager:
    """
    The 5-Layer Shield. Injects rebrowser patches, sets user-agent,
    mocks hardware (WebGL, Battery, Sensors), and ensures CDP isolation.
    """

    def __init__(self) -> None:
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None

    async def launch(self, headless: bool = True) -> Page:
        """Launch a stealth-configured browser and return a page."""
        self.playwright = await async_playwright().start()

        # Select random mobile user agent
        user_agent = random.choice(MOBILE_USER_AGENTS)

        logger.info(f"Launching stealth browser with UA: {user_agent[:60]}...")

        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=BROWSER_LAUNCH_ARGS,
        )

        self.context = await self.browser.new_context(
            viewport=VIEWPORT_CONFIG,
            user_agent=user_agent,
            device_scale_factor=DEVICE_SCALE_FACTOR,
            is_mobile=True,
            has_touch=True,
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            geolocation=GEOLOCATION_INDIA,
            permissions=["geolocation"],
            color_scheme="light",
        )

        # Inject stealth evasion scripts
        await self._inject_stealth_scripts()

        self.page = await self.context.new_page()
        await self._apply_additional_evasions()

        logger.info("Stealth browser launched successfully.")
        return self.page

    async def _inject_stealth_scripts(self) -> None:
        """Inject JavaScript evasions for webdriver, WebGL, plugins, battery."""
        scripts = [
            # Webdriver evasion
            """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            """,
            # Chrome runtime evasion
            """
            window.chrome = { runtime: {} };
            """,
            # Plugins evasion
            """
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    {name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer'},
                    {name: 'Native Client', filename: 'native-client.dll'}
                ]
            });
            """,
            # WebGL vendor evasion
            """
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) return 'Apple Inc.';
                if (parameter === 37446) return 'Apple GPU';
                return getParameter(parameter);
            };
            """,
            # Battery API mock
            """
            if ('getBattery' in navigator) {
                navigator.getBattery = async () => ({
                    charging: true,
                    chargingTime: 0,
                    dischargingTime: Infinity,
                    level: 0.95,
                    addEventListener: () => {},
                    removeEventListener: () => {},
                });
            }
            """,
            # Permissions API mock
            """
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : originalQuery(parameters)
            );
            """,
        ]

        for script in scripts:
            await self.context.add_init_script(script)

        logger.debug("Stealth scripts injected.")

    async def _apply_additional_evasions(self) -> None:
        """Apply page-level evasions after page creation."""
        await self.page.evaluate("""
            () => {
                // Overwrite the `plugins` property to appear real
                Object.defineProperty(navigator, 'mimeTypes', {
                    get: () => ({ length: 2, item: () => null })
                });
                // Fake languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-IN', 'en-US', 'en']
                });
                // Override notification permissions
                const originalNotification = window.Notification;
                Object.defineProperty(window, 'Notification', {
                    get: () => originalNotification,
                    set: () => {}
                });
            }
        """)

    async def inject_cookies(self, cookie_json: str, domain_filter: Optional[str] = None) -> None:
        """Parse and inject cookies into the browser context."""
        try:
            cookies: List[Dict[str, Any]] = json.loads(cookie_json)
            if domain_filter:
                cookies = [c for c in cookies if domain_filter in c.get("domain", "")]
            await self.context.add_cookies(cookies)
            logger.info(f"Injected {len(cookies)} cookies into browser context.")
        except json.JSONDecodeError as exc:
            logger.error(f"Cookie parsing failed: {exc}")
            raise ValueError(f"Invalid cookie JSON: {exc}") from exc

    async def close(self) -> None:
        """Gracefully close browser and playwright."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("Stealth browser closed.")

    async def capture_error_state(self, output_dir: str = "media/error_logs") -> str:
        """Capture screenshot and DOM dump for debugging failures."""
        import os
        from datetime import datetime, timezone

        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        screenshot_path = f"{output_dir}/error_screenshot_{timestamp}.png"
        dom_path = f"{output_dir}/error_dom_{timestamp}.html"

        if self.page:
            await self.page.screenshot(path=screenshot_path, full_page=True)
            dom_content = await self.page.content()
            with open(dom_path, "w", encoding="utf-8") as f:
                f.write(dom_content)
            logger.info(f"Error state captured: {screenshot_path}, {dom_path}")

        return screenshot_path
