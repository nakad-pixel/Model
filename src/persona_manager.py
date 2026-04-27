"""
Project Astra - Persona Manager
Multi-persona coordinator with subdirectory isolation.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.reference.embedding_generator import EmbeddingGenerator
from src.reference.face_verifier import FaceVerifier
from src.reference.hash_store import HashStore
from src.reference.reference_manager import ReferenceManager
from src.utils.cookie_manager import CookieManager
from src.utils.logger import logger


@dataclass
class PersonaConfig:
    """Configuration for a single persona."""

    persona_id: str
    posting_windows: List[Dict[str, int]] = field(default_factory=lambda: [
        {"start": 8, "end": 10},
        {"start": 20, "end": 22},
    ])
    max_daily_posts: int = 2
    min_hours_between_posts: int = 4
    state_path: str = ""

    def __post_init__(self) -> None:
        if not self.state_path:
            self.state_path = f"data/{self.persona_id}/state_log.json"


class PersonaManager:
    """
    Coordinates multiple personas with full isolation.
    Each persona has: state, references, embeddings, hashes, cookies.
    """

    DEFAULT_PERSONA_ID: str = "astra"

    def __init__(self, persona_id: Optional[str] = None) -> None:
        self.persona_id = persona_id or os.getenv("PERSONA_ID", self.DEFAULT_PERSONA_ID)
        self.config = PersonaConfig(persona_id=self.persona_id)

        # Per-persona subsystems
        self.reference_manager = ReferenceManager(self.persona_id)
        self.embedding_generator = EmbeddingGenerator(self.persona_id)
        self.face_verifier = FaceVerifier(self.persona_id)
        self.hash_store = HashStore(self.persona_id)
        self.cookie_manager = CookieManager(self.persona_id)

        # Ensure directory structure exists
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        dirs = [
            f"data/{self.persona_id}",
            f"data/{self.persona_id}/reference",
            f"data/{self.persona_id}/embeddings",
            f"data/{self.persona_id}/hashes",
            f"data/{self.persona_id}/cookies",
            f"data/{self.persona_id}/lora_training",
        ]
        for d in dirs:
            Path(d).mkdir(parents=True, exist_ok=True)

    def setup_references(self, candidate_paths: Optional[List[str]] = None) -> List[Path]:
        """
        Set up canonical reference images for the persona.
        If candidates provided, store them. Otherwise check if already present.
        Returns list of canonical paths.
        """
        if candidate_paths:
            for idx, path in enumerate(candidate_paths[: ReferenceManager.CANONICAL_COUNT], start=1):
                self.reference_manager.store_candidate(path, idx)

        canonicals = self.reference_manager.get_canonical_paths()
        if len(canonicals) == ReferenceManager.CANONICAL_COUNT:
            # Generate embeddings and hashes
            self.embedding_generator.generate_embeddings(canonicals)
            self.hash_store.add_reference_hashes(canonicals)
            logger.info(f"Persona '{self.persona_id}' references initialized with {len(canonicals)} images.")
        else:
            logger.warning(
                f"Persona '{self.persona_id}' has only {len(canonicals)}/{ReferenceManager.CANONICAL_COUNT} references."
            )

        return canonicals

    def verify_media(self, media_path: str) -> Dict[str, Any]:
        """
        Run full verification pipeline on generated media.
        Returns dict with face_verification and phash_drift results.
        """
        face_ok, face_score = self.face_verifier.verify(media_path)
        phash_ok, phash_dist = self.hash_store.check_drift(media_path)

        result = {
            "face_verified": face_ok,
            "face_similarity": face_score,
            "phash_acceptable": phash_ok,
            "phash_distance": phash_dist,
            "overall_pass": face_ok and phash_ok,
        }

        if result["overall_pass"]:
            self.hash_store.accept_image(media_path)
        else:
            self.hash_store.reject_image(media_path, reason="verification_failure")

        return result

    def get_cookies_for_platform(self, platform: str) -> Optional[str]:
        """Get raw cookie JSON for a specific platform."""
        return self.cookie_manager.load_cookies(platform)

    def get_all_cookie_health(self) -> Dict[str, Any]:
        """Return cookie health report for this persona."""
        return self.cookie_manager.full_health_report()

    def inject_prompt_with_references(self, prompt: str) -> str:
        """Augment a generation prompt with reference persona descriptors."""
        return self.reference_manager.inject_reference_context(prompt)

    @classmethod
    def list_personas(cls) -> List[str]:
        """Scan data/ directory and return discovered persona IDs."""
        data_dir = Path("data")
        if not data_dir.exists():
            return []
        return [d.name for d in data_dir.iterdir() if d.is_dir()]
