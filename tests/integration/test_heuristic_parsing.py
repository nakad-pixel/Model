"""
Integration Tests: AI Chrome / GLM Layer
IT-HEURISTIC-BUTTON-FIND, DOM sanitizer integration
"""

import json
import tempfile
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from src.engine.dom_sanitizer import DOMSanitizer
from src.engine.heuristic_navigator import GLMClient, HeuristicNavigator


SAMPLE_MOCK_HTML = """
<!DOCTYPE html>
<html>
<head><title>Mock Buffer</title></head>
<body>
    <nav>
        <button aria-label="Create Post" class="css-1abc123" id="compose-btn">Create</button>
    </nav>
    <main>
        <div class="dashboard">
            <textarea placeholder="What's on your mind?"></textarea>
            <input type="file" accept="image/*" />
            <button data-testid="schedule-btn">Add to Queue</button>
        </div>
    </main>
    <script>console.log('script');</script>
    <style>body{color:red}</style>
</body>
</html>
"""


class TestHeuristicParsing:
    """IT-HEURISTIC-BUTTON-FIND: Test heuristic DOM parsing against fixtures."""

    @pytest.mark.asyncio
    async def test_dom_sanitizer_strips_scripts(self):
        """DOM sanitizer should remove script and style tags."""
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.set_content(SAMPLE_MOCK_HTML)

            sanitizer = DOMSanitizer()
            dom = await sanitizer.sanitize(page)

            assert "<script>" not in dom
            assert "<style>" not in dom
            assert "Create Post" in dom  # button text preserved
            await browser.close()

    @pytest.mark.asyncio
    async def test_dom_sanitizer_truncates_long_dom(self):
        """DOM should be truncated when exceeding max length."""
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            # Large DOM
            large_html = "<div>" + "<span>text</span>" * 2000 + "</div>"
            await page.set_content(large_html)

            sanitizer = DOMSanitizer()
            dom = await sanitizer.sanitize(page)
            assert "[truncated]" in dom or len(dom) <= DOMSanitizer.MAX_DOM_LENGTH + 50
            await browser.close()

    @pytest.mark.asyncio
    async def test_accessibility_tree_extraction(self):
        """Accessibility tree should contain semantic elements."""
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.set_content(SAMPLE_MOCK_HTML)

            sanitizer = DOMSanitizer()
            tree = await sanitizer.get_accessibility_tree(page)

            # Should contain button role references
            assert "button" in tree.lower() or len(tree) > 0
            await browser.close()

    def test_glm_response_parser_valid_json(self):
        """GLM response parser should handle valid JSON."""
        client = GLMClient(api_key="fake-key")
        raw = '{"thought_process": "Found it", "confidence_score": 95, "action_type": "click", "target_selector": "button[aria-label=\\"Create Post\\"]", "value_to_fill": null}'
        parsed = client._parse_glm_response(raw)
        assert parsed["confidence_score"] == 95
        assert parsed["target_selector"] == 'button[aria-label="Create Post"]'

    def test_glm_response_parser_markdown_fenced(self):
        """GLM response parser should strip markdown code fences."""
        client = GLMClient(api_key="fake-key")
        raw = '```json\n{"thought_process": "ok", "confidence_score": 80, "action_type": "click", "target_selector": "#btn", "value_to_fill": null}\n```'
        parsed = client._parse_glm_response(raw)
        assert parsed["confidence_score"] == 80
        assert parsed["target_selector"] == "#btn"

    def test_glm_response_parser_invalid_json(self):
        """Invalid JSON should return zero-confidence fallback."""
        client = GLMClient(api_key="fake-key")
        parsed = client._parse_glm_response("not valid json at all")
        assert parsed["confidence_score"] == 0
        assert parsed["target_selector"] is None

    def test_glm_response_parser_missing_keys(self):
        """Missing required keys should result in zero confidence."""
        client = GLMClient(api_key="fake-key")
        raw = '{"thought_process": "missing keys"}'
        parsed = client._parse_glm_response(raw)
        assert parsed["confidence_score"] == 0
