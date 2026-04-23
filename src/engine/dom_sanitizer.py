"""
Project Astra - DOM Sanitizer
Strips non-visual tags and extracts accessibility tree for LLM context optimization.
"""

from typing import Optional

from playwright.async_api import Page

from src.utils.logger import logger


class DOMSanitizer:
    """Sanitizes DOM content to fit within LLM context windows."""

    MAX_DOM_LENGTH: int = 8000  # Characters to keep DOM within context limits

    @staticmethod
    async def sanitize(page: Page) -> str:
        """
        Extract a simplified DOM representation by removing scripts,
        styles, and non-semantic tags. Returns truncated HTML string.
        """
        sanitized = await page.evaluate(
            """
            () => {
                const clone = document.body.cloneNode(true);
                const removeTags = ['script', 'style', 'link', 'svg', 'path', 'meta', 'noscript', 'iframe', 'canvas'];
                removeTags.forEach(tag => {
                    clone.querySelectorAll(tag).forEach(el => el.remove());
                });
                // Remove hidden elements
                clone.querySelectorAll('[hidden], [style*="display:none"], [style*="display: none"]').forEach(el => el.remove());
                return clone.innerHTML;
            }
            """
        )
        result = str(sanitized) if sanitized else ""

        if len(result) > DOMSanitizer.MAX_DOM_LENGTH:
            result = result[:DOMSanitizer.MAX_DOM_LENGTH] + "\n...[truncated]"

        logger.debug(f"DOM sanitized. Length: {len(result)} chars")
        return result

    @staticmethod
    async def get_accessibility_tree(page: Page) -> str:
        """
        Extract accessibility tree via CDP for semantic element identification.
        """
        try:
            # Use CDP to fetch accessibility tree snapshot
            cdp_session = await page.context.new_cdp_session(page)
            snapshot = await cdp_session.send("Accessibility.getFullAXTree")
            await cdp_session.detach()

            # Simplify tree for LLM consumption
            nodes = snapshot.get("nodes", [])
            simplified = DOMSanitizer._simplify_ax_tree(nodes)
            return simplified
        except Exception as exc:
            logger.warning(f"Accessibility tree extraction failed: {exc}. Falling back to DOM.")
            return await DOMSanitizer.sanitize(page)

    @staticmethod
    def _simplify_ax_tree(nodes: list) -> str:
        """Convert AXTree nodes to a simple text representation."""
        lines = []
        for node in nodes[:100]:  # Limit nodes for context window
            role = node.get("role", "")
            name = node.get("name", "")
            if role and name:
                lines.append(f"[{role}] {name}")
        return "\n".join(lines[:200])

    @staticmethod
    async def get_element_text_map(page: Page) -> str:
        """
        Extract a mapping of visible text elements with their tag names.
        Useful for GLM to identify buttons and links by text content.
        """
        elements = await page.query_selector_all(
            'button, a, div[role="button"], input, textarea, [contenteditable="true"]'
        )
        text_map: list[str] = []
        for idx, el in enumerate(elements[:50]):
            tag = await el.evaluate("el => el.tagName.toLowerCase()")
            text = await el.evaluate("el => (el.innerText || el.value || el.placeholder || '').trim().slice(0, 100)")
            aria = await el.evaluate("el => el.getAttribute('aria-label') || ''")
            if text or aria:
                entry = f"[{idx}] <{tag}> text='{text}' aria='{aria}'"
                text_map.append(entry)
        return "\n".join(text_map)
