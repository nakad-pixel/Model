"""
Project Astra - Prompt Synthesizer
Constructs persona-consistent image prompts based on time-of-day context.
"""

import random
from datetime import datetime
from typing import Optional

from src.constants import (
    BASE_DNA_STRING,
    EVENING_LIGHTING,
    EVENING_SCENES,
    MORNING_LIGHTING,
    MORNING_SCENES,
    TECHNICAL_MODIFIERS,
)
from src.utils.logger import logger


class PromptSynthesizer:
    """Logic for persona consistency and contextual variety in image prompts."""

    def __init__(self, last_theme_used: Optional[str] = None) -> None:
        self.last_theme_used = last_theme_used
        self.base_dna = BASE_DNA_STRING
        self.morning_scenes = MORNING_SCENES.copy()
        self.evening_scenes = EVENING_SCENES.copy()

    def get_daily_prompt(self, forced_time_of_day: Optional[str] = None) -> str:
        """
        Generate a full image prompt based on time of day (IST).
        Ensures the same scene modifier is not used consecutively.
        """
        time_of_day = forced_time_of_day or self._detect_time_of_day()

        if time_of_day == "morning":
            scene = self._select_scene(self.morning_scenes)
            lighting = MORNING_LIGHTING
        else:
            scene = self._select_scene(self.evening_scenes)
            lighting = EVENING_LIGHTING

        # Build final prompt
        prompt = f"{self.base_dna}. {scene}. {lighting}. {TECHNICAL_MODIFIERS}."

        self.last_theme_used = scene
        logger.info(f"Generated prompt for {time_of_day}: {prompt[:120]}...")
        return prompt

    def get_prompt_with_context(self, context: str) -> str:
        """Generate a prompt with a specific user-provided context."""
        prompt = f"{self.base_dna}. {context}. {TECHNICAL_MODIFIERS}."
        logger.info(f"Generated custom context prompt: {prompt[:120]}...")
        return prompt

    @staticmethod
    def _detect_time_of_day() -> str:
        """Detect morning or evening based on current IST time."""
        from zoneinfo import ZoneInfo

        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        hour = now.hour

        if 5 <= hour < 17:
            return "morning"
        return "evening"

    def _select_scene(self, scenes: list[str]) -> str:
        """Select a scene, avoiding the last used theme if possible."""
        available = [s for s in scenes if s != self.last_theme_used]
        if not available:
            available = scenes
        return random.choice(available)
