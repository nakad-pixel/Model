"""
Project Astra - Platform Router
AI-driven platform selection based on content analysis scores.
"""

from typing import Dict, List, Tuple

from src.utils.logger import logger


class PlatformRouter:
    """
    Routes content to the optimal generation platform based on
    motion_score, quality_score, and availability_score.
    """

    @staticmethod
    def select_video_platform(
        motion_score: float,
        quality_score: float,
        availability_score: float,
    ) -> Tuple[str, List[str]]:
        """
        Select the best video platform and fallback chain.
        Args:
            motion_score: 0.0-1.0, likelihood of motion-heavy content.
            quality_score: 0.0-1.0, desired cinematic quality.
            availability_score: 0.0-1.0, platform health status.
        Returns:
            Tuple of (primary_platform, fallback_chain).
        """
        platforms: List[Tuple[str, float]] = []

        # Wan.video excels at motion-heavy content
        wan_score = motion_score * 0.6 + availability_score * 0.4
        platforms.append(("wan", wan_score))

        # Veo 3 excels at cinematic quality
        veo_score = quality_score * 0.6 + availability_score * 0.4
        platforms.append(("veo", veo_score))

        # Kie is the reliable fallback
        kie_score = availability_score * 0.5 + (1.0 - max(motion_score, quality_score)) * 0.3
        platforms.append(("kie", kie_score))

        # Sort by score descending
        platforms.sort(key=lambda x: x[1], reverse=True)
        primary = platforms[0][0]
        fallback_chain = [p[0] for p in platforms[1:]]

        logger.info(
            f"PlatformRouter: primary={primary}, fallback={fallback_chain}, "
            f"scores=wan:{platforms[0][1]:.2f},veo:{platforms[1][1]:.2f},kie:{platforms[2][1]:.2f}"
        )
        return primary, fallback_chain

    @staticmethod
    def analyze_prompt_keywords(prompt: str) -> Dict[str, float]:
        """
        Heuristic keyword analysis to estimate content scores.
        Returns motion_score, quality_score based on prompt text.
        """
        prompt_lower = prompt.lower()

        motion_keywords = [
            "walking", "dancing", "running", "exercising", "moving", "spinning",
            "jumping", "skating", "waving", "gesturing", "action", "motion",
            "dynamic", "kinetic", "dance", "workout", "yoga flow",
        ]
        cinematic_keywords = [
            "cinematic", "film", "movie", "directed", "dramatic", "slow motion",
            "golden hour", "neon", "moody", "atmospheric", "bokeh", "depth",
            "anamorphic", "wide shot", "close up", "tracking", "dolly",
        ]

        motion_hits = sum(1 for kw in motion_keywords if kw in prompt_lower)
        cinematic_hits = sum(1 for kw in cinematic_keywords if kw in prompt_lower)

        motion_score = min(motion_hits / 3.0, 1.0)
        quality_score = min(cinematic_hits / 3.0, 1.0)

        return {"motion_score": motion_score, "quality_score": quality_score}
