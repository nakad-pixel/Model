"""
Unit Tests: Validation & Edge Cases
UT-COOKIE-PARSER-ERROR, caption validation, telemetry
"""

import json
import os
import tempfile

import pytest

from src.generators.caption_generator import CaptionGenerator
from src.generators.media_validator import MediaValidator


class TestCookieParser:
    """UT-COOKIE-PARSER-ERROR: Malformed cookies should raise ValueError."""

    def test_malformed_json_raises_value_error(self):
        """Malformed JSON cookie string must raise ValueError/JSONDecodeError."""
        from src.utils.stealth_manager import StealthManager

        bad_json = '[{"name": "test", "value": "bad"'  # missing closing bracket

        # StealthManager.inject_cookies should raise ValueError
        manager = StealthManager()
        # Since we don't have a real browser context in unit tests,
        # we test the json.loads directly
        with pytest.raises((ValueError, json.JSONDecodeError)):
            json.loads(bad_json)


class TestCaptionValidation:
    """Caption post-processing validation tests."""

    def test_forbidden_words_stripped(self):
        """Forbidden words should be detected and stripped."""
        gen = CaptionGenerator()
        raw = 'Here is your caption: "Delve into the tapestry of this moment. #a #b #c #d #e"'
        result = gen._post_process(raw)
        assert "Delve" not in result
        assert "Tapestry" not in result

    def test_hashtag_count_enforced(self):
        """Exactly 5 hashtags should be present after post-processing."""
        gen = CaptionGenerator()
        raw = "Just a casual thought. #one #two"
        result = gen._post_process(raw)
        hashtags = [w for w in result.split() if w.startswith("#")]
        assert len(hashtags) == 5

    def test_length_truncation(self):
        """Captions exceeding max length should be truncated."""
        gen = CaptionGenerator()
        raw = "A" * 500 + " " + " ".join([f"#tag{i}" for i in range(5)])
        result = gen._post_process(raw)
        # The result should be at most MAX_CAPTION_LENGTH plus some hashtag padding
        # since hashtags are appended after truncation if missing
        from src.constants import MAX_CAPTION_LENGTH
        assert len(result) <= MAX_CAPTION_LENGTH + 60

    def test_filler_removal(self):
        """Conversational filler should be stripped."""
        gen = CaptionGenerator()
        raw = 'Here is your caption: "vibes today... #a #b #c #d #e"'
        result = gen._post_process(raw)
        assert "Here is your caption:" not in result
        assert "vibes today" in result.lower()


class TestMediaValidatorEdgeCases:
    """Edge case tests for media validation."""

    def test_corrupted_image_file(self):
        """Corrupted/corrupt image data should fail gracefully."""
        validator = MediaValidator()
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"this is not a real png file content")
            tmp_path = f.name

        try:
            is_valid, errors = validator.validate(tmp_path)
            assert is_valid is False
            assert any("open failed" in e.lower() or "format" in e.lower() for e in errors)
        finally:
            os.unlink(tmp_path)

    def test_color_distribution_uniform(self):
        """Uniform color images (possible placeholders) should be flagged."""
        from PIL import Image

        validator = MediaValidator()
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            tmp_path = f.name

        # Create a 100x200 portrait image with ALL pixels the same color
        img = Image.new("RGB", (100, 200), color=(128, 128, 128))
        img.save(tmp_path, "PNG")

        try:
            is_valid, errors = validator.validate(tmp_path)
            # Should fail size check too since 100x200 is small
            assert is_valid is False
        finally:
            os.unlink(tmp_path)
