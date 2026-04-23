"""
Integration Tests: Gemini Extraction Logic
IT-CAPTION-GENERATION, image extraction polling simulation
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.generators.caption_generator import CaptionGenerator


class TestCaptionGeneration:
    """IT-CAPTION-GENERATION: Test caption generation and validation."""

    def test_post_process_extracts_hashtags(self):
        """Exactly 5 hashtags should be extracted and validated."""
        gen = CaptionGenerator(api_key="fake")
        raw = "Just thinking about today. What are you working on? #code #design #aesthetic #morning #vibes"
        result = gen._post_process(raw)
        hashtags = [w for w in result.split() if w.startswith("#")]
        assert len(hashtags) == 5

    def test_post_process_adds_missing_hashtags(self):
        """Missing hashtags should be appended."""
        gen = CaptionGenerator(api_key="fake")
        raw = "Long day..."
        result = gen._post_process(raw)
        hashtags = [w for w in result.split() if w.startswith("#")]
        assert len(hashtags) == 5

    def test_post_process_removes_quotes(self):
        """Surrounding quotes should be stripped."""
        gen = CaptionGenerator(api_key="fake")
        raw = '"vibes today... #a #b #c #d #e"'
        result = gen._post_process(raw)
        assert not result.startswith('"')
        assert not result.endswith('"')

    def test_post_process_enforces_max_length(self):
        """Captions should not exceed MAX_CAPTION_LENGTH plus hashtag padding."""
        gen = CaptionGenerator(api_key="fake")
        from src.constants import MAX_CAPTION_LENGTH
        raw = "A" * 400 + " " + " ".join([f"#t{i}" for i in range(5)])
        result = gen._post_process(raw)
        # Truncation happens, but hashtag append may add a small padding
        assert len(result) <= MAX_CAPTION_LENGTH + 60


class TestVisionFallback:
    """Vision fallback coordinate parsing tests."""

    def test_coordinate_parser_valid_json(self):
        """Valid coordinate JSON should parse correctly."""
        from src.engine.vision_fallback import VisionFallback

        fallback = VisionFallback(api_key="fake")
        raw = '{"x": 150, "y": 300, "confidence": 85}'
        parsed = fallback._parse_coordinate_response(raw)
        assert parsed["x"] == 150
        assert parsed["y"] == 300
        assert parsed["confidence"] == 85

    def test_coordinate_parser_markdown_stripped(self):
        """Markdown fences should be stripped from vision response."""
        from src.engine.vision_fallback import VisionFallback

        fallback = VisionFallback(api_key="fake")
        raw = '```json\n{"x": 100, "y": 200, "confidence": 90}\n```'
        parsed = fallback._parse_coordinate_response(raw)
        assert parsed["x"] == 100
        assert parsed["y"] == 200

    def test_coordinate_parser_invalid_returns_zero(self):
        """Invalid response should return zero coordinates."""
        from src.engine.vision_fallback import VisionFallback

        fallback = VisionFallback(api_key="fake")
        parsed = fallback._parse_coordinate_response("not json")
        assert parsed["confidence"] == 0
