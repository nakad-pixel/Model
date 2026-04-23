"""
Unit Tests: State Manager Logic
"""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.constants import DEFAULT_STATE
from src.utils.state_manager import StateManager


class TestStateLogic:
    """Tests for atomic state read/write and daily counter reset."""

    def test_load_creates_default_when_missing(self):
        """StateManager should initialize defaults when file missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state_log.json"
            manager = StateManager(str(path))
            state = manager.load()
            assert state["version"] == DEFAULT_STATE["version"]
            assert path.exists()

    def test_load_merges_with_defaults(self):
        """Partial state files should be merged with default schema."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state_log.json"
            partial = {"daily_post_count": 5}
            with open(path, "w") as f:
                json.dump(partial, f)

            manager = StateManager(str(path))
            state = manager.load()
            assert state["daily_post_count"] == 5
            assert state["version"] == DEFAULT_STATE["version"]

    def test_atomic_write_creates_file(self):
        """Atomic write should create the state file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state_log.json"
            manager = StateManager(str(path))
            manager.update_and_save({"daily_post_count": 3})
            assert path.exists()
            with open(path) as f:
                data = json.load(f)
            assert data["daily_post_count"] == 3

    def test_corrupt_file_resets_to_defaults(self):
        """Corrupt JSON should reset to defaults without crashing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state_log.json"
            with open(path, "w") as f:
                f.write("{ invalid json")

            manager = StateManager(str(path))
            state = manager.load()
            assert state["version"] == DEFAULT_STATE["version"]

    def test_reset_daily_counters(self):
        """Counters should reset when date changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state_log.json"
            yesterday = datetime.now(timezone.utc).replace(day=1)
            if yesterday.day == 1:
                yesterday = yesterday.replace(month=max(1, yesterday.month - 1))

            with open(path, "w") as f:
                json.dump({
                    "last_execution_timestamp_utc": yesterday.isoformat(),
                    "daily_post_count": 2,
                }, f)

            manager = StateManager(str(path))
            state = manager.reset_daily_counters_if_needed()
            assert state["daily_post_count"] == 0

    def test_increment_counter(self):
        """Increment counter should bump the value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state_log.json"
            manager = StateManager(str(path))
            state = manager.increment_counter("daily_post_count")
            assert state["daily_post_count"] == 1
