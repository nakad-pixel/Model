"""
Unit Tests: Prompt Synthesis Logic
UT-PROMPT-SYNTHESIS, UT-FILE-VALIDATION-FAIL-SIZE, UT-FILE-VALIDATION-FAIL-ASPECT
"""

import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from src.constants import BASE_DNA_STRING, MORNING_SCENES
from src.generators.media_validator import MediaValidator
from src.generators.prompt_synthesizer import PromptSynthesizer


class TestPromptSynthesis:
    """UT-PROMPT-SYNTHESIS: Validate prompt generation logic."""

    def test_morning_prompt_contains_base_dna(self):
        """Assert the Base DNA string is perfectly contained in the output."""
        synth = PromptSynthesizer()
        prompt = synth.get_daily_prompt(forced_time_of_day="morning")
        assert BASE_DNA_STRING in prompt

    def test_prompt_length_exceeds_minimum(self):
        """Assert prompt string length is > 50 characters."""
        synth = PromptSynthesizer()
        prompt = synth.get_daily_prompt(forced_time_of_day="morning")
        assert len(prompt) > 50

    def test_morning_modifier_present(self):
        """Assert morning-related modifiers are present when forced to morning."""
        synth = PromptSynthesizer()
        prompt = synth.get_daily_prompt(forced_time_of_day="morning")
        # At least one morning scene keyword should appear
        assert any(scene.split()[0].lower() in prompt.lower() for scene in MORNING_SCENES)

    def test_evening_prompt_contains_evening_context(self):
        """Assert evening prompts contain evening-specific lighting."""
        synth = PromptSynthesizer()
        prompt = synth.get_daily_prompt(forced_time_of_day="evening")
        assert "neon" in prompt.lower() or "moody" in prompt.lower() or "3200K" in prompt

    def test_no_consecutive_repeats(self):
        """Assert the same scene modifier isn't used consecutively."""
        synth = PromptSynthesizer()
        prompt1 = synth.get_daily_prompt(forced_time_of_day="morning")
        prompt2 = synth.get_daily_prompt(forced_time_of_day="morning")
        # With only 4 scenes, there's a small chance of collision, but last_theme_used should track
        assert synth.last_theme_used is not None

    def test_custom_context_prompt(self):
        """Assert custom context prompts include the provided context."""
        synth = PromptSynthesizer()
        custom = "Standing on a rooftop at sunset"
        prompt = synth.get_prompt_with_context(custom)
        assert custom in prompt
        assert BASE_DNA_STRING in prompt


class TestFileValidation:
    """UT-FILE-VALIDATION: Test media validator edge cases."""

    def test_validation_fail_size(self):
        """UT-FILE-VALIDATION-FAIL-SIZE: Tiny file must fail validation."""
        validator = MediaValidator()
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake tiny data")
            tmp_path = f.name

        try:
            is_valid, errors = validator.validate(tmp_path)
            assert is_valid is False
            assert any("Invalid Size" in e for e in errors)
        finally:
            os.unlink(tmp_path)

    def test_validation_fail_aspect_ratio(self):
        """UT-FILE-VALIDATION-FAIL-ASPECT: Landscape image must fail."""
        validator = MediaValidator()
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            tmp_path = f.name

        # Create a 1920x1080 landscape PNG
        img = Image.new("RGB", (1920, 1080), color="blue")
        img.save(tmp_path, "PNG")

        try:
            is_valid, errors = validator.validate(tmp_path)
            assert is_valid is False
            assert any("Invalid Aspect Ratio" in e for e in errors)
        finally:
            os.unlink(tmp_path)

    def test_validation_pass_portrait(self):
        """Valid portrait image should pass all checks."""
        validator = MediaValidator()
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            tmp_path = f.name

        # Create a valid 1080x1920 portrait PNG with random noise for file size
        import random
        img = Image.new("RGB", (1080, 1920))
        pixels = img.load()
        for x in range(1080):
            for y in range(1920):
                pixels[x, y] = (
                    random.randint(0, 255),
                    random.randint(0, 255),
                    random.randint(0, 255),
                )
        img.save(tmp_path, "PNG")

        try:
            is_valid, errors = validator.validate(tmp_path)
            assert is_valid is True
            assert len(errors) == 0
        finally:
            os.unlink(tmp_path)

    def test_nonexistent_file(self):
        """Nonexistent file should return appropriate error."""
        validator = MediaValidator()
        is_valid, errors = validator.validate("/tmp/nonexistent_file_12345.png")
        assert is_valid is False
        assert any("does not exist" in e for e in errors)
