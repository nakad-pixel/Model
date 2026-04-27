"""
Unit Tests: Persona Manager & Cookie Manager
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from src.persona_manager import PersonaConfig, PersonaManager
from src.utils.cookie_manager import CookieManager


class TestPersonaConfig:
    """Tests for persona configuration dataclass."""

    def test_default_state_path(self):
        """Default state path should include persona_id."""
        cfg = PersonaConfig(persona_id="nova")
        assert "nova" in cfg.state_path

    def test_posting_windows(self):
        """Default posting windows should be configured."""
        cfg = PersonaConfig(persona_id="astra")
        assert len(cfg.posting_windows) == 2


class TestCookieManager:
    """Tests for per-persona cookie management."""

    def test_env_key_format(self):
        """Environment key should be uppercase with persona suffix."""
        mgr = CookieManager(persona_id="astra")
        assert mgr.get_env_key("gemini") == "GEMINI_COOKIES_ASTRA"

    def test_parse_valid_cookies(self):
        """Valid JSON cookie list should parse correctly."""
        mgr = CookieManager(persona_id="test")
        raw = '[{"name": "session", "value": "abc123"}]'
        cookies = mgr.parse_cookies(raw)
        assert len(cookies) == 1
        assert cookies[0]["name"] == "session"

    def test_parse_invalid_json(self):
        """Invalid JSON should return empty list."""
        mgr = CookieManager(persona_id="test")
        cookies = mgr.parse_cookies("not json")
        assert cookies == []

    def test_health_check_no_cookies(self):
        """Health check with no cookies should be unhealthy."""
        mgr = CookieManager(persona_id="test_nocookies")
        health = mgr.health_check("gemini")
        assert health.healthy is False
        assert health.score == 0.0

    def test_full_health_report(self):
        """Full report should cover all platforms."""
        mgr = CookieManager(persona_id="test_report")
        report = mgr.full_health_report()
        assert "platforms" in report
        assert report["overall_healthy"] in (True, False)


class TestPersonaManager:
    """Tests for multi-persona coordinator."""

    def test_persona_id_from_env(self):
        """Persona ID should default from env or constant."""
        mgr = PersonaManager()
        assert mgr.persona_id is not None

    def test_directories_created(self):
        """Constructor should create persona subdirectories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original = os.getcwd()
            os.chdir(tmpdir)
            try:
                mgr = PersonaManager(persona_id="test_dirs")
                assert Path("data/test_dirs/reference").exists()
                assert Path("data/test_dirs/embeddings").exists()
                assert Path("data/test_dirs/hashes").exists()
                assert Path("data/test_dirs/cookies").exists()
            finally:
                os.chdir(original)

    def test_inject_prompt_with_references(self):
        """Prompt injection should append persona descriptor when references exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original = os.getcwd()
            os.chdir(tmpdir)
            try:
                mgr = PersonaManager(persona_id="test_prompt")
                # Create a canonical reference so descriptor is injected
                from PIL import Image
                ref_dir = Path(tmpdir) / "data" / "test_prompt" / "reference"
                ref_dir.mkdir(parents=True, exist_ok=True)
                img_path = Path(tmpdir) / "source_1.png"
                Image.new("RGB", (100, 200), color="blue").save(img_path)
                mgr.reference_manager.store_candidate(str(img_path), 1)

                prompt = "A scenic landscape"
                result = mgr.inject_prompt_with_references(prompt)
                assert "honey blonde" in result.lower()
            finally:
                os.chdir(original)

    def test_verify_media_no_references(self):
        """Verification without references should still complete."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original = os.getcwd()
            os.chdir(tmpdir)
            try:
                mgr = PersonaManager(persona_id="test_verify")
                # Create a dummy image
                from PIL import Image

                img_path = Path(tmpdir) / "dummy.png"
                Image.new("RGB", (1080, 1920), color="red").save(img_path)
                result = mgr.verify_media(str(img_path))
                assert "face_verified" in result
                assert "phash_acceptable" in result
            finally:
                os.chdir(original)
