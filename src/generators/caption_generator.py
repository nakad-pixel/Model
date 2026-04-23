"""
Project Astra - Caption Generator
GLM-4.7 interface for aesthetic text and hashtag generation.
"""

import os
import re
from typing import Optional

import httpx

from src.constants import (
    ALLOWED_PHRASES,
    FORBIDDEN_WORDS,
    HASHTAG_COUNT,
    MAX_CAPTION_LENGTH,
    PRIMARY_EMOJIS,
    SECONDARY_EMOJIS,
)
from src.utils.logger import logger


class CaptionGenerator:
    """Generates human-like captions in Astra's voice using GLM-4.7."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.getenv("GLM_API_KEY")
        self.base_url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

    async def generate(
        self,
        context: str,
        time_of_day: str = "morning",
        curiosity_gap: bool = False,
    ) -> Optional[str]:
        """
        Generate a caption based on visual context.
        Returns validated caption string or None.
        """
        if not self.api_key:
            logger.error("GLM_API_KEY not configured for caption generation.")
            return None

        system_prompt = (
            "You are Astra, a 24-year-old digital creator and UI/UX designer. "
            "You are warm, confident, slightly witty, observant, and relatable. "
            "You speak casually. Utilize a lower-case aesthetic occasionally. "
            "You do NOT sound like an AI assistant or a corporate brand. "
            "STRICT LENGTH: 1 to 2 short sentences. Max 1-2 emojis total. "
            "Append exactly 5 highly relevant SEO hashtags at the very end, separated by spaces. "
            "FORBIDDEN WORDS: Delve, Tapestry, Furthermore, In conclusion, Hey guys, Link in bio, As an AI."
        )

        user_prompt = f"""
Write an Instagram caption based on this visual context: {context}
Time of day: {time_of_day}.
Rules:
- Max 2 sentences.
- Use 1-2 emojis total.
- Do not use hashtags in the main text body.
- Tone: Casual, lower-case aesthetic, authentic.
- Append exactly 5 hashtags at the very end.
"""
        if curiosity_gap:
            user_prompt += (
                "\nAdd a subtle curiosity gap about exclusive content 'on the private feed'. "
                "Make it sound like a secret shared with a close friend."
            )

        payload = {
            "model": "glm-4",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.8,
            "max_tokens": 256,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.base_url,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

            raw_caption = data["choices"][0]["message"]["content"].strip()
            return self._post_process(raw_caption)

        except Exception as exc:
            logger.error(f"Caption generation failed: {exc}")
            return None

    def _post_process(self, raw: str) -> Optional[str]:
        """Clean and validate the generated caption."""
        # Strip conversational filler
        fillers = [
            "Here is your caption:",
            "Here is the caption:",
            "Caption:",
            "Here you go:",
        ]
        for filler in fillers:
            raw = raw.replace(filler, "").strip()

        # Remove surrounding quotes
        raw = raw.strip('"').strip("'")

        # Validate forbidden words
        lower_raw = raw.lower()
        for word in FORBIDDEN_WORDS:
            if word.lower() in lower_raw:
                logger.warning(f"Forbidden word detected in caption: {word}")
                raw = raw.replace(word, "")

        # Validate length
        if len(raw) > MAX_CAPTION_LENGTH:
            logger.warning(f"Caption too long ({len(raw)} chars). Truncating.")
            raw = raw[:MAX_CAPTION_LENGTH]

        # Validate hashtag count
        hashtags = re.findall(r"#\w+", raw)
        if len(hashtags) != HASHTAG_COUNT:
            logger.warning(f"Expected {HASHTAG_COUNT} hashtags, found {len(hashtags)}. Adjusting.")
            # Simple fallback: append generic hashtags if missing
            if len(hashtags) < HASHTAG_COUNT:
                needed = HASHTAG_COUNT - len(hashtags)
                extras = ["#lifestyle", "#aesthetic", "#creativelife", "#designer", "#morningvibes"][:needed]
                raw = raw + " " + " ".join(extras)

        return raw.strip()
