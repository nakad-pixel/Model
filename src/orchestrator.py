"""
Project Astra - Orchestrator
Main state machine managing the agent lifecycle from initialization to posting.
Multi-persona architecture with reference consistency verification.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from src.constants import (
    DEFAULT_PERSONA_ID,
    DEFAULT_STATE,
    EVENING_WINDOW_END,
    EVENING_WINDOW_START,
    MAX_CONSECUTIVE_FAILURES,
    MAX_DAILY_POSTS,
    MAX_GENERATION_RETRIES,
    MIN_HOURS_BETWEEN_POSTS,
    MORNING_WINDOW_END,
    MORNING_WINDOW_START,
)
from src.engine.interaction_handler import InteractionHandler
from src.generators.caption_generator import CaptionGenerator
from src.generators.gemini_client import GeminiClient
from src.generators.media_validator import MediaValidator
from src.generators.prompt_synthesizer import PromptSynthesizer
from src.generators.video_client import VideoClient
from src.persona_manager import PersonaManager
from src.platforms.buffer import BufferPlatform
from src.platforms.clipchamp import ClipchampPlatform
from src.platforms.metricool import MetricoolPlatform
from src.platforms.social_champ import SocialChampPlatform
from src.utils.biometric_sim import BiometricSimulator
from src.utils.cost_tracker import CostTracker
from src.utils.logger import logger
from src.utils.network_healer import NetworkHealer
from src.utils.state_manager import StateManager
from src.utils.stealth_manager import StealthManager
from src.utils.telemetry import Telemetry
from src.utils.warp_manager import WarpManager


class OrchestratorState(Enum):
    IDLE = auto()
    INITIALIZING = auto()
    LOADING_PERSONA = auto()
    GENERATING_REFERENCE = auto()
    GENERATING_MEDIA = auto()
    VALIDATING = auto()
    GENERATING_CAPTION = auto()
    POSTING = auto()
    LOGGING = auto()
    FINISHING = auto()


class Orchestrator:
    """
    The brain of Project Astra. Manages state transitions,
    circuit breaker logic, persona isolation, and coordinates all subsystems.
    """

    def __init__(self, persona_id: Optional[str] = None) -> None:
        self.persona_id = persona_id or os.getenv("PERSONA_ID", DEFAULT_PERSONA_ID)
        self.state = OrchestratorState.IDLE
        self.state_manager = StateManager(persona_id=self.persona_id)
        self.telemetry = Telemetry()
        self.warp = WarpManager()
        self.network_healer = NetworkHealer(self.warp)
        self.stealth: Optional[StealthManager] = None
        self.page = None
        self.cost_tracker = CostTracker()
        self.persona_manager = PersonaManager(self.persona_id)

        # Generators
        self.prompt_synthesizer: Optional[PromptSynthesizer] = None
        self.gemini_client: Optional[GeminiClient] = None
        self.video_client: Optional[VideoClient] = None
        self.media_validator = MediaValidator()
        self.caption_generator = CaptionGenerator()

        # Platforms
        self.buffer: Optional[BufferPlatform] = None
        self.metricool: Optional[MetricoolPlatform] = None
        self.social_champ: Optional[SocialChampPlatform] = None
        self.clipchamp: Optional[ClipchampPlatform] = None

        # Tracking
        self.current_prompt: Optional[str] = None
        self.media_path: Optional[str] = None
        self.caption: Optional[str] = None
        self.phase_error: Optional[str] = None
        self.is_video: bool = False

    async def run(self) -> int:
        """
        Main orchestrator loop. Returns exit code (0 for success/no-op, 1 for failure).
        """
        try:
            # Phase: INITIALIZING
            await self._transition_to(OrchestratorState.INITIALIZING)
            if not await self._initialize():
                logger.info("Orchestrator exiting: initialization gate prevented run.")
                return 0

            # Phase: LOADING_PERSONA
            await self._transition_to(OrchestratorState.LOADING_PERSONA)
            if not await self._load_persona():
                await self._handle_failure("LOADING_PERSONA")
                return 1

            # Phase: GENERATING_MEDIA
            await self._transition_to(OrchestratorState.GENERATING_MEDIA)
            if not await self._generate_media():
                await self._handle_failure("GENERATING_MEDIA")
                return 1

            # Phase: VALIDATING
            await self._transition_to(OrchestratorState.VALIDATING)
            if not await self._validate_media():
                await self._handle_failure("VALIDATING")
                return 1

            # Phase: GENERATING_CAPTION
            await self._transition_to(OrchestratorState.GENERATING_CAPTION)
            if not await self._generate_caption():
                await self._handle_failure("GENERATING_CAPTION")
                return 1

            # Phase: POSTING
            await self._transition_to(OrchestratorState.POSTING)
            if not await self._post_content():
                await self._handle_failure("POSTING")
                return 1

            # Phase: LOGGING
            await self._transition_to(OrchestratorState.LOGGING)
            await self._log_success()

            # Phase: FINISHING
            await self._transition_to(OrchestratorState.FINISHING)
            await self._cleanup()

            logger.info("Orchestrator completed successfully.")
            return 0

        except Exception as exc:
            logger.exception("Unhandled exception in orchestrator")
            await self._handle_failure(f"UNHANDLED_EXCEPTION: {exc}")
            return 1

    async def _initialize(self) -> bool:
        """
        Initialize state, check scheduling gates, connect WARP, launch browser.
        Returns False if execution should be skipped.
        """
        # Load and reset daily counters if needed
        state = self.state_manager.reset_daily_counters_if_needed()

        # Gate 1: Check consecutive failures (circuit breaker)
        consecutive_failures = state.get("consecutive_failures", 0)
        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            logger.error(f"Circuit breaker active: {consecutive_failures} consecutive failures.")
            await self.telemetry.send_failure(
                "INITIALIZING",
                f"Circuit breaker tripped: {consecutive_failures} consecutive failures.",
            )
            return False

        # Gate 2: Check posting windows (IST)
        now_ist = datetime.now(timezone.utc).astimezone(ZoneInfo("Asia/Kolkata"))
        hour = now_ist.hour + now_ist.minute / 60

        in_morning_window = MORNING_WINDOW_START <= hour < MORNING_WINDOW_END
        in_evening_window = EVENING_WINDOW_START <= hour < EVENING_WINDOW_END

        if not (in_morning_window or in_evening_window):
            logger.info(
                f"Outside posting windows (IST hour={hour:.2f}). Exiting gracefully."
            )
            return False

        time_of_day = "morning" if in_morning_window else "evening"

        # Gate 3: Minimum hours between posts
        last_ts = state.get("last_execution_timestamp_utc")
        if last_ts:
            last_dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
            hours_since = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
            if hours_since < MIN_HOURS_BETWEEN_POSTS:
                logger.info(f"Only {hours_since:.1f}h since last post. Min: {MIN_HOURS_BETWEEN_POSTS}h.")
                return False

        # Gate 4: Daily post limit
        daily_count = state.get("daily_post_count", 0)
        if daily_count >= MAX_DAILY_POSTS:
            logger.info(f"Daily post limit reached: {daily_count}/{MAX_DAILY_POSTS}")
            return False

        # Initialize components
        self.prompt_synthesizer = PromptSynthesizer(
            last_theme_used=state.get("last_theme_used")
        )

        # Connect WARP (Layer 1)
        if os.getenv("SKIP_WARP") != "true":
            await self.warp.install()
            await self.warp.register()
            if not await self.warp.connect():
                logger.warning("WARP connection failed. Proceeding without WARP.")

        # Network self-healing check
        healthy = await self.network_healer.health_check()
        if not healthy[0]:
            healed = await self.network_healer.heal_if_needed()
            if not healed:
                logger.error("Network self-healing failed. Aborting.")
                await self.telemetry.send_failure(
                    "INITIALIZING",
                    "Network self-healing failed after WARP reconnect.",
                )
                return False

        # Launch stealth browser (Layers 2-3)
        self.stealth = StealthManager()
        self.page = await self.stealth.launch(headless=os.getenv("HEADED") != "true")

        # Inject per-persona cookies (Layer 5)
        cookie_mgr = self.persona_manager.cookie_manager
        for platform in cookie_mgr.all_platforms():
            raw_cookies = cookie_mgr.load_cookies(platform)
            if raw_cookies:
                domain_filter = None
                if platform == "gemini":
                    domain_filter = "google.com"
                elif platform in ("wan", "kie", "buffer", "metricool"):
                    domain_filter = f"{platform}"
                try:
                    await self.stealth.inject_cookies(raw_cookies, domain_filter=domain_filter)
                except Exception as exc:
                    logger.warning(f"Cookie injection failed for {platform}: {exc}")

        # Initialize subsystems
        interaction = InteractionHandler(self.page)
        self.gemini_client = GeminiClient(self.page, interaction)
        self.video_client = VideoClient(
            self.page,
            interaction,
            network_healer=self.network_healer,
            telemetry=self.telemetry,
            cost_tracker=self.cost_tracker,
        )
        self.buffer = BufferPlatform(self.page, interaction)
        self.metricool = MetricoolPlatform(self.page, interaction)
        self.social_champ = SocialChampPlatform(self.page, interaction)
        self.clipchamp = ClipchampPlatform(self.page, interaction)

        # Check cookie health and alert if needed
        cookie_alerts = cookie_mgr.should_alert()
        if cookie_alerts:
            for platform in cookie_alerts:
                await self.telemetry.send_cookie_expired(platform)

        logger.info(f"Initialization complete for persona '{self.persona_id}'. Time of day: {time_of_day}")
        return True

    async def _load_persona(self) -> bool:
        """
        Load persona configuration and verify canonical references exist.
        If references are missing, attempt to set up from candidates.
        """
        ref_mgr = self.persona_manager.reference_manager
        if not ref_mgr.all_canonicals_exist():
            logger.warning(
                f"Persona '{self.persona_id}' missing canonical references. "
                "Please provide 5 reference images in data/{persona_id}/reference/"
            )
            # Gracefully continue without references; verification will be skipped
        else:
            logger.info(f"Persona '{self.persona_id}' canonical references verified.")
            # Ensure embeddings and hashes are initialized
            canonicals = ref_mgr.get_canonical_paths()
            self.persona_manager.setup_references()
        return True

    async def _generate_media(self) -> bool:
        """
        Generate image or video based on AI content decision.
        AI decides when to use video vs static image.
        Injects reference persona descriptors for consistency.
        """
        if not self.prompt_synthesizer:
            return False

        state = self.state_manager.load()
        generation_attempt = state.get("generation_attempt", 0)

        for attempt in range(MAX_GENERATION_RETRIES + 1):
            base_prompt = self.prompt_synthesizer.get_daily_prompt()
            # Inject reference context for persona consistency
            self.current_prompt = self.persona_manager.inject_prompt_with_references(base_prompt)
            logger.info(f"Generation attempt {attempt + 1}: {self.current_prompt[:100]}...")

            # AI content decision: analyze prompt for video suitability
            analysis = await self.video_client.analyze_content_for_video(self.current_prompt)
            use_video = analysis.get("use_video", False)
            motion_score = analysis.get("motion_score", 0.0)
            cinematic_score = analysis.get("cinematic_score", 0.0)

            logger.info(
                f"Content analysis: use_video={use_video}, motion={motion_score:.2f}, cinematic={cinematic_score:.2f}"
            )

            if use_video:
                self.is_video = True
                self.media_path = await self.video_client.generate_video(
                    self.current_prompt,
                    motion_score=motion_score,
                    cinematic_score=cinematic_score,
                )
            else:
                self.is_video = False
                self.media_path = await self.gemini_client.generate_image(self.current_prompt)

            if self.media_path and Path(self.media_path).exists():
                self.state_manager.update_and_save({"generation_attempt": 0})
                return True

            generation_attempt += 1
            self.state_manager.update_and_save({"generation_attempt": generation_attempt})
            logger.warning(f"Generation attempt {attempt + 1} failed. Retrying...")
            await asyncio.sleep(5)

        logger.error("All generation attempts exhausted.")
        return False

    async def _validate_media(self) -> bool:
        """Validate generated media quality and persona consistency."""
        if not self.media_path:
            return False

        # For video, do basic file validation
        if self.is_video:
            path = Path(self.media_path)
            if path.exists() and path.stat().st_size > 50_000:
                export_path = f"media/exports/{path.name}"
                Path(export_path).parent.mkdir(parents=True, exist_ok=True)
                path.rename(export_path)
                self.media_path = export_path
                logger.info(f"Video validation passed: {self.media_path}")
                return True
            logger.error("Video validation failed: file too small or missing.")
            return False

        # Image validation pipeline
        is_valid, errors = self.media_validator.validate(self.media_path)
        if not is_valid:
            logger.error(f"Media validation failed: {errors}")
            return False

        # Persona consistency verification (face + pHash)
        ref_mgr = self.persona_manager.reference_manager
        if ref_mgr.all_canonicals_exist():
            verify_result = self.persona_manager.verify_media(self.media_path)
            if not verify_result["overall_pass"]:
                logger.error(
                    f"Persona consistency failed: face={verify_result['face_verified']}, "
                    f"phash={verify_result['phash_acceptable']}"
                )
                return False
            logger.info(
                f"Persona consistency passed: similarity={verify_result['face_similarity']:.3f}, "
                f"phash_dist={verify_result['phash_distance']}"
            )

        export_path = f"media/exports/{Path(self.media_path).name}"
        Path(export_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.media_path).rename(export_path)
        self.media_path = export_path
        return True

    async def _generate_caption(self) -> bool:
        """Generate caption using GLM-4.7."""
        if not self.current_prompt:
            return False

        time_of_day = self.prompt_synthesizer._detect_time_of_day() if self.prompt_synthesizer else "morning"
        curiosity = time_of_day == "evening"

        self.caption = await self.caption_generator.generate(
            context=self.current_prompt,
            time_of_day=time_of_day,
            curiosity_gap=curiosity,
        )

        if self.caption:
            logger.info(f"Caption generated: {self.caption[:100]}...")
            return True

        logger.error("Caption generation returned None.")
        return False

    async def _post_content(self) -> bool:
        """Post content to available schedulers."""
        if not self.media_path or not self.caption:
            return False

        # Try platforms in order of preference
        if self.is_video:
            platforms = [
                ("buffer", self.buffer),
                ("metricool", self.metricool),
                ("clipchamp", self.clipchamp),
                ("social_champ", self.social_champ),
            ]
        else:
            platforms = [
                ("buffer", self.buffer),
                ("metricool", self.metricool),
                ("social_champ", self.social_champ),
                ("clipchamp", self.clipchamp),
            ]

        for name, platform in platforms:
            if platform is None:
                continue
            try:
                logger.info(f"Attempting to post via {name}...")

                # Platform health check before posting
                if hasattr(platform, "BUFFER_URL"):
                    healthy = await self.network_healer.platform_health_check(platform.BUFFER_URL)
                elif hasattr(platform, "METRICOOL_URL"):
                    healthy = await self.network_healer.platform_health_check(platform.METRICOOL_URL)
                elif hasattr(platform, "CLIPCHAMP_URL"):
                    healthy = await self.network_healer.platform_health_check(platform.CLIPCHAMP_URL)
                else:
                    healthy = True

                if not healthy:
                    logger.warning(f"Skipping {name}: platform health check failed.")
                    continue

                success = await platform.create_post(self.media_path, self.caption)
                if success:
                    logger.info(f"Posted successfully via {name}.")
                    await self.telemetry.send_success(
                        context=f"Persona: {self.persona_id} | Platform: {name} | Type: {'video' if self.is_video else 'image'} | Prompt: {self.current_prompt[:80]}...",
                        image_path=None if self.is_video else self.media_path,
                    )
                    return True
            except Exception as exc:
                logger.error(f"Platform {name} error: {exc}")
                if "401" in str(exc) or "403" in str(exc) or "login" in str(exc).lower():
                    await self.telemetry.send_cookie_expired(name)

        logger.error("All platforms failed to accept the post.")
        return False

    async def _log_success(self) -> None:
        """Update state log with success metrics."""
        now = datetime.now(timezone.utc).isoformat()
        updates = {
            "last_execution_timestamp_utc": now,
            "daily_post_count": self.state_manager.load().get("daily_post_count", 0) + 1,
            "last_theme_used": self.current_prompt,
            "consecutive_failures": 0,
            "total_posts_all_time": self.state_manager.load().get("total_posts_all_time", 0) + 1,
        }
        self.state_manager.update_and_save(updates)

        # Check cost tracker alerts
        alert_msg = self.cost_tracker.check_and_alert()
        if alert_msg:
            await self.telemetry.send_failure("COST_TRACKER", alert_msg)

        logger.info("State log updated with success.")

    async def _handle_failure(self, phase: str) -> None:
        """Handle failure: increment counter, capture state, alert."""
        self.phase_error = phase
        state = self.state_manager.load()
        consecutive = state.get("consecutive_failures", 0) + 1
        self.state_manager.update_and_save({"consecutive_failures": consecutive})

        screenshot_path = None
        if self.stealth:
            screenshot_path = await self.stealth.capture_error_state()

        await self.telemetry.send_failure(phase, f"Failure in phase {phase}", screenshot_path)
        logger.error(f"Orchestrator failure in phase: {phase}. Consecutive: {consecutive}")

        # Circuit breaker: same phase fails 3x -> go dark + alert
        if consecutive >= MAX_CONSECUTIVE_FAILURES:
            logger.critical("Circuit breaker tripped. Agent going dark.")
            await self.telemetry.send_failure(
                "CIRCUIT_BREAKER",
                f"Agent going dark after {consecutive} consecutive failures.",
                screenshot_path,
            )

    async def _cleanup(self) -> None:
        """Graceful shutdown: close browser, disconnect WARP."""
        if self.stealth:
            await self.stealth.close()
        await self.warp.disconnect()
        logger.info("Cleanup complete.")

    async def _transition_to(self, new_state: OrchestratorState) -> None:
        """Log state transitions and persist phase-level state."""
        logger.info(f"State transition: {self.state.name} -> {new_state.name}")
        self.state = new_state
        # Phase-level state saving for recovery
        self.state_manager.update_and_save({"current_phase": new_state.name})


def main() -> int:
    """Synchronous entry point for orchestrator."""
    orchestrator = Orchestrator()
    return asyncio.run(orchestrator.run())


if __name__ == "__main__":
    sys.exit(main())
