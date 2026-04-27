"""
Project Astra - State Manager
Atomic JSON read/write for state_log.json corruption prevention.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from src.constants import DEFAULT_STATE
from src.utils.logger import logger


class StateManager:
    """Atomic handling of the agent's memory and execution state."""

    def __init__(self, path: str = "", persona_id: str = "") -> None:
        if path:
            self.path = Path(path)
        elif persona_id:
            self.path = Path(f"data/{persona_id}/state_log.json")
        else:
            self.path = Path("data/state_log.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Dict[str, Any]:
        """Load state from disk, initializing defaults if missing."""
        if not self.path.exists():
            logger.warning(f"State file not found at {self.path}. Initializing defaults.")
            default = DEFAULT_STATE.copy()
            self._atomic_write(default)
            return default

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                state = json.load(f)
            # Merge with defaults to ensure schema completeness
            merged = {**DEFAULT_STATE, **state}
            return merged
        except (json.JSONDecodeError, OSError) as exc:
            logger.error(f"State file corrupt or unreadable: {exc}. Resetting to defaults.")
            default = DEFAULT_STATE.copy()
            self._atomic_write(default)
            return default

    def update_and_save(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update state with atomic write to prevent corruption during crashes."""
        current_state = self.load()
        current_state.update(updates)
        self._atomic_write(current_state)
        logger.debug(f"State updated: {updates.keys()}")
        return current_state

    def _atomic_write(self, state: Dict[str, Any]) -> None:
        """Write state to temp file then replace for atomicity."""
        temp_path = self.path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4, ensure_ascii=False)
        os.replace(temp_path, self.path)
        logger.debug(f"State atomically written to {self.path}")

    def reset_daily_counters_if_needed(self) -> Dict[str, Any]:
        """Reset daily post count if the date has rolled over."""
        from datetime import datetime, timezone

        state = self.load()
        last_ts = state.get("last_execution_timestamp_utc")
        now = datetime.now(timezone.utc)

        if last_ts:
            try:
                last_dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                if last_dt.date() != now.date():
                    logger.info("New day detected. Resetting daily_post_count.")
                    return self.update_and_save({"daily_post_count": 0})
            except ValueError:
                logger.warning("Invalid timestamp in state. Resetting daily count.")
                return self.update_and_save({"daily_post_count": 0})

        return state

    def increment_counter(self, key: str, reset_key: Optional[str] = None) -> Dict[str, Any]:
        """Increment a numeric counter in the state."""
        state = self.load()
        current = state.get(key, 0)
        updates = {key: current + 1}
        if reset_key:
            updates[reset_key] = 0
        return self.update_and_save(updates)
