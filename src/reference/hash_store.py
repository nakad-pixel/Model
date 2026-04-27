"""
Project Astra - Hash Store
Perceptual hash (pHash) drift detection for generated media.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import imagehash
from PIL import Image

from src.utils.logger import logger


class HashStore:
    """
    Stores and compares perceptual hashes of accepted/generated images
    to detect visual drift from the canonical persona.
    """

    DRIFT_THRESHOLD: int = 12  # Hamming distance threshold for pHash drift

    def __init__(self, persona_id: str = "astra") -> None:
        self.persona_id = persona_id
        self.hash_dir = Path(f"data/{persona_id}/hashes")
        self.hash_dir.mkdir(parents=True, exist_ok=True)
        self.store_path = self.hash_dir / "accepted_hashes.json"
        self._data = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.store_path.exists():
            try:
                with open(self.store_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(f"Hash store corrupt: {exc}. Starting fresh.")
        return {"accepted": [], "rejected": [], "version": "2026.6.0"}

    def _save(self) -> None:
        temp = self.store_path.with_suffix(".tmp")
        with open(temp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)
        os.replace(temp, self.store_path)

    def compute_phash(self, image_path: str) -> Optional[str]:
        """Compute pHash string for an image."""
        try:
            with Image.open(image_path) as img:
                phash = str(imagehash.phash(img))
                return phash
        except Exception as exc:
            logger.error(f"pHash computation failed for {image_path}: {exc}")
            return None

    def add_reference_hashes(self, image_paths: List[Path]) -> None:
        """Add canonical reference image hashes as accepted baseline."""
        for path in image_paths:
            phash = self.compute_phash(str(path))
            if phash:
                entry = {"path": str(path), "phash": phash, "type": "canonical"}
                if entry not in self._data["accepted"]:
                    self._data["accepted"].append(entry)
        self._save()
        logger.info(f"Added {len(image_paths)} reference hashes for {self.persona_id}")

    def check_drift(self, image_path: str) -> Tuple[bool, int]:
        """
        Check if a generated image has drifted from accepted hashes.
        Returns (is_acceptable, min_hamming_distance).
        """
        phash_str = self.compute_phash(image_path)
        if not phash_str:
            return False, 999

        test_hash = imagehash.hex_to_hash(phash_str)
        min_distance = 999

        for entry in self._data["accepted"]:
            accepted_hash = imagehash.hex_to_hash(entry["phash"])
            distance = test_hash - accepted_hash
            if distance < min_distance:
                min_distance = distance

        is_acceptable = min_distance <= self.DRIFT_THRESHOLD
        if is_acceptable:
            logger.info(f"pHash drift check PASSED (distance={min_distance}): {image_path}")
        else:
            logger.warning(f"pHash drift check FAILED (distance={min_distance}): {image_path}")

        return is_acceptable, min_distance

    def accept_image(self, image_path: str) -> None:
        """Add a generated image hash to the accepted set."""
        phash = self.compute_phash(image_path)
        if phash:
            entry = {"path": image_path, "phash": phash, "type": "generated"}
            self._data["accepted"].append(entry)
            self._save()

    def reject_image(self, image_path: str, reason: str = "drift") -> None:
        """Record a rejected image for audit."""
        phash = self.compute_phash(image_path)
        entry = {"path": image_path, "phash": phash or "", "reason": reason}
        self._data["rejected"].append(entry)
        self._save()

    def get_drift_report(self) -> Dict[str, Any]:
        """Return summary of accepted/rejected images and drift stats."""
        return {
            "persona_id": self.persona_id,
            "accepted_count": len(self._data["accepted"]),
            "rejected_count": len(self._data["rejected"]),
            "drift_threshold": self.DRIFT_THRESHOLD,
        }
