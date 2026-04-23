"""
Project Astra - Heuristic Navigator
Connects Playwright to GLM-4.7 for AI-powered DOM element identification.
"""

import base64
import json
import os
from typing import Any, Dict, Optional

import httpx
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from src.constants import CONFIDENCE_THRESHOLD, FALLBACK_SELECTORS
from src.engine.dom_sanitizer import DOMSanitizer
from src.utils.logger import logger


class GLMClient:
    """Async client for GLM-4.7 heuristic reasoning API."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.getenv("GLM_API_KEY")
        self.base_url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

    async def parse_ui(
        self,
        dom_snippet: str,
        screenshot_b64: Optional[str],
        objective: str,
    ) -> Dict[str, Any]:
        """
        Send DOM + screenshot to GLM-4.7 and request a CSS selector.
        Returns structured JSON with reasoning, confidence, action, and selector.
        """
        if not self.api_key:
            raise ValueError("GLM_API_KEY not configured.")

        system_prompt = (
            "You are the 'AI Chrome' visual cortex for an autonomous Playwright system. "
            "Analyze raw DOM structures and identify the exact, most resilient CSS Selector "
            "required to fulfill a specific user intent/action. "
            "You MUST respond with a perfectly valid, parseable JSON object ONLY. "
            "No Markdown, no conversational filler. "
            "JSON Structure: {\"thought_process\": string, \"confidence_score\": 0-100 integer, "
            "\"action_type\": \"click|fill|scroll|wait\", \"target_selector\": string, "
            "\"value_to_fill\": string or null}"
        )

        user_content = f"""
Objective: {objective}

DOM Snippet:
{dom_snippet[:4000]}

Find the element and return the JSON response.
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        # If screenshot available, add vision content
        if screenshot_b64:
            messages[1]["content"] = [
                {"type": "text", "text": user_content},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}},
            ]

        payload = {
            "model": "glm-4",
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 512,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                self.base_url,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        raw_content = data["choices"][0]["message"]["content"]
        return self._parse_glm_response(raw_content)

    def _parse_glm_response(self, raw: str) -> Dict[str, Any]:
        """Extract and validate JSON from GLM response."""
        # Strip markdown code fences if present
        clean = raw.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        if clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        clean = clean.strip()

        try:
            parsed = json.loads(clean)
            # Validate required keys
            required = {"thought_process", "confidence_score", "action_type", "target_selector"}
            if not required.issubset(parsed.keys()):
                missing = required - parsed.keys()
                logger.warning(f"GLM response missing keys: {missing}")
                parsed["confidence_score"] = 0
                parsed["target_selector"] = None
            return parsed
        except json.JSONDecodeError as exc:
            logger.error(f"Failed to parse GLM response as JSON: {exc}. Raw: {raw[:200]}")
            return {
                "thought_process": "JSON parse failed",
                "confidence_score": 0,
                "action_type": "wait",
                "target_selector": None,
                "value_to_fill": None,
            }


class HeuristicNavigator:
    """The bridge between Playwright and LLM reasoning for UI automation."""

    def __init__(self, page: Page, api_key: Optional[str] = None, retry_count: int = 2) -> None:
        self.page = page
        self.glm_client = GLMClient(api_key)
        self.retry_count = retry_count
        self.dom_sanitizer = DOMSanitizer()

    async def find_element(self, objective: str, use_vision: bool = True) -> Optional[str]:
        """
        Query GLM-4.7 to locate an element by objective.
        Returns target_selector string or None if not found.
        """
        dom_snippet = await self.dom_sanitizer.sanitize(self.page)
        screenshot_b64 = None
        if use_vision:
            screenshot = await self.page.screenshot(type="png", full_page=False)
            screenshot_b64 = base64.b64encode(screenshot).decode("utf-8")

        for attempt in range(self.retry_count + 1):
            try:
                result = await self.glm_client.parse_ui(dom_snippet, screenshot_b64, objective)
                confidence = result.get("confidence_score", 0)
                selector = result.get("target_selector")

                if confidence >= CONFIDENCE_THRESHOLD and selector:
                    # Verify selector resolves
                    try:
                        await self.page.wait_for_selector(selector, timeout=3000)
                        logger.info(f"Heuristic found element: {selector} (confidence: {confidence})")
                        return selector
                    except PlaywrightTimeoutError:
                        logger.warning(f"Selector resolved by GLM but not found in DOM: {selector}")
                else:
                    logger.warning(f"Low confidence ({confidence}) or no selector. Retrying...")

                # Fallback: scroll and re-evaluate
                if attempt < self.retry_count:
                    await self.page.evaluate("window.scrollBy(0, 200)")
                    await self.page.wait_for_timeout(500)
                    dom_snippet = await self.dom_sanitizer.sanitize(self.page)

            except Exception as exc:
                logger.error(f"Heuristic navigation error (attempt {attempt + 1}): {exc}")
                if attempt < self.retry_count:
                    await self.page.wait_for_timeout(5000)

        logger.error(f"Heuristic navigator failed to find element for objective: {objective}")
        return None

    async def perform_action(self, intent: str, value: Optional[str] = None) -> bool:
        """
        Use GLM-4.7 to identify an element and perform the action (click/fill/scroll/wait).
        Returns True if action succeeded.
        """
        selector = await self.find_element(intent)
        if not selector:
            logger.error(f"Could not find element for intent: {intent}")
            return False

        try:
            element = await self.page.query_selector(selector)
            if not element:
                logger.error(f"Element not found with selector: {selector}")
                return False

            tag = await element.evaluate("el => el.tagName.toLowerCase()")
            input_type = await element.evaluate("el => el.type || ''")
            is_editable = tag in ("input", "textarea") or await element.evaluate(
                "el => el.isContentEditable"
            )

            if value and is_editable:
                await element.fill(value)
                logger.info(f"Filled element {selector} with value.")
            else:
                await element.click()
                logger.info(f"Clicked element: {selector}")

            return True
        except Exception as exc:
            logger.error(f"Action failed on {selector}: {exc}")
            return False

    def get_fallback_selector(self, key: str) -> Optional[str]:
        """Retrieve a fallback selector from constants when GLM is unavailable."""
        return FALLBACK_SELECTORS.get(key)
