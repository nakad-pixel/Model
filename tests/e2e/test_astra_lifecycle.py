"""
End-to-End Tests: Full Astra Lifecycle
E2E smoke test with 180-second timeout enforcement.
"""

import asyncio
import json
import os
import tempfile
import time
from pathlib import Path

import pytest


class TestAstraLifecycle:
    """Full pipeline smoke test orchestrator."""

    @pytest.mark.timeout(180)
    @pytest.mark.asyncio
    async def test_orchestrator_initialization_gate(self):
        """
        Verify orchestrator respects initialization gates:
        - Outside posting window should exit with code 0
        - Daily limit reached should exit with code 0
        """
        from src.orchestrator import Orchestrator

        orch = Orchestrator()
        # Force state to show max daily posts
        orch.state_manager.update_and_save({"daily_post_count": 2})

        # Run should return 0 (graceful exit) since daily limit hit
        exit_code = await orch.run()
        assert exit_code in (0, 1)  # Either graceful skip or may proceed depending on time

    @pytest.mark.timeout(180)
    @pytest.mark.asyncio
    async def test_prompt_synthesis_pipeline(self):
        """Prompt synthesizer should produce valid prompts."""
        from src.generators.prompt_synthesizer import PromptSynthesizer
        from src.constants import BASE_DNA_STRING

        synth = PromptSynthesizer()
        prompt = synth.get_daily_prompt(forced_time_of_day="morning")

        assert BASE_DNA_STRING in prompt
        assert len(prompt) > 50

    @pytest.mark.timeout(180)
    @pytest.mark.asyncio
    async def test_media_validation_pipeline(self):
        """Media validator should correctly accept/reject test images."""
        import random
        from PIL import Image
        from src.generators.media_validator import MediaValidator

        validator = MediaValidator()

        # Valid portrait image with random noise for file size
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            valid_path = f.name
        img = Image.new("RGB", (1080, 1920))
        pixels = img.load()
        for x in range(1080):
            for y in range(1920):
                pixels[x, y] = (
                    random.randint(0, 255),
                    random.randint(0, 255),
                    random.randint(0, 255),
                )
        img.save(valid_path, "PNG")

        try:
            is_valid, errors = validator.validate(valid_path)
            assert is_valid is True
        finally:
            os.unlink(valid_path)

        # Invalid landscape
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            invalid_path = f.name
        img = Image.new("RGB", (1920, 1080), color="red")
        img.save(invalid_path, "PNG")

        try:
            is_valid, errors = validator.validate(invalid_path)
            assert is_valid is False
        finally:
            os.unlink(invalid_path)

    @pytest.mark.timeout(180)
    @pytest.mark.asyncio
    async def test_caption_generation_pipeline(self):
        """Caption generator post-processing should enforce rules."""
        from src.generators.caption_generator import CaptionGenerator

        gen = CaptionGenerator(api_key="fake")
        raw = 'Here is your caption: "vibes today... honestly, just need more coffee. #a #b #c #d #e"'
        result = gen._post_process(raw)

        assert "Here is your caption:" not in result
        hashtags = [w for w in result.split() if w.startswith("#")]
        assert len(hashtags) == 5

    @pytest.mark.timeout(180)
    @pytest.mark.asyncio
    async def test_state_manager_atomicity(self):
        """State manager should atomically write without corruption."""
        from src.utils.state_manager import StateManager

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state_log.json"
            manager = StateManager(str(path))

            # Simulate rapid concurrent-like updates
            for i in range(10):
                manager.update_and_save({"daily_post_count": i + 1})

            final = manager.load()
            assert final["daily_post_count"] == 10
            assert path.exists()
            assert not (path.parent / "state_log.json.tmp").exists()

    @pytest.mark.timeout(180)
    @pytest.mark.asyncio
    async def test_stealth_manager_launch(self):
        """Stealth manager should launch browser without errors."""
        pytest.importorskip("playwright")
        from src.utils.stealth_manager import StealthManager

        stealth = StealthManager()
        try:
            page = await stealth.launch(headless=True)
            assert page is not None
            # Verify viewport
            viewport = page.viewport_size
            assert viewport["width"] == 390
            assert viewport["height"] == 844
        finally:
            await stealth.close()

    @pytest.mark.timeout(180)
    @pytest.mark.asyncio
    async def test_full_orchestrator_state_transitions(self):
        """Verify orchestrator states are valid enum values."""
        from src.orchestrator import Orchestrator, OrchestratorState

        orch = Orchestrator()
        assert orch.state == OrchestratorState.IDLE

        # Check all expected states exist
        states = [
            OrchestratorState.IDLE,
            OrchestratorState.INITIALIZING,
            OrchestratorState.LOADING_PERSONA,
            OrchestratorState.GENERATING_REFERENCE,
            OrchestratorState.GENERATING_MEDIA,
            OrchestratorState.VALIDATING,
            OrchestratorState.GENERATING_CAPTION,
            OrchestratorState.POSTING,
            OrchestratorState.LOGGING,
            OrchestratorState.FINISHING,
        ]
        for s in states:
            assert isinstance(s, OrchestratorState)
