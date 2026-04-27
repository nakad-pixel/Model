"""
Project Astra - Face Verifier
Compares generated media against reference embeddings for persona consistency.
"""

from pathlib import Path
from typing import Optional, Tuple

import numpy as np
from PIL import Image

from src.reference.embedding_generator import EmbeddingGenerator
from src.utils.logger import logger


class FaceVerifier:
    """
    Verifies that generated images contain the same persona face
    by comparing embeddings against canonical references.
    """

    DEFAULT_SIMILARITY_THRESHOLD: float = 0.60  # Cosine similarity threshold

    def __init__(
        self,
        persona_id: str = "astra",
        threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    ) -> None:
        self.persona_id = persona_id
        self.threshold = threshold
        self.embedding_generator = EmbeddingGenerator(persona_id)
        self._face_recognition_available = self.embedding_generator._face_recognition_available

    def verify(self, image_path: str) -> Tuple[bool, float]:
        """
        Verify a generated image against reference embeddings.
        Returns (is_consistent, confidence_score).
        """
        path = Path(image_path)
        if not path.exists():
            logger.error(f"Image not found for verification: {image_path}")
            return False, 0.0

        mean_emb = self.embedding_generator.get_mean_embedding("face_recognition")
        if mean_emb is None:
            logger.warning("No reference embeddings available. Skipping face verification.")
            return True, 1.0  # Pass-through if no references

        if not self._face_recognition_available:
            logger.debug("face_recognition not available. Skipping verification.")
            return True, 1.0

        try:
            import face_recognition

            img = face_recognition.load_image_file(str(path))
            encodings = face_recognition.face_encodings(img)
            if not encodings:
                logger.warning(f"No face detected in generated image: {image_path}")
                return False, 0.0

            gen_emb = encodings[0]
            similarity = self._cosine_similarity(mean_emb, gen_emb)
            is_consistent = similarity >= self.threshold

            if is_consistent:
                logger.info(f"Face verification PASSED (similarity={similarity:.3f}): {path.name}")
            else:
                logger.warning(f"Face verification FAILED (similarity={similarity:.3f}): {path.name}")

            return is_consistent, float(similarity)

        except Exception as exc:
            logger.error(f"Face verification error: {exc}")
            return False, 0.0

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        dot = np.dot(a, b)
        norm = np.linalg.norm(a) * np.linalg.norm(b)
        if norm == 0:
            return 0.0
        return float(dot / norm)

    def verify_batch(self, image_paths: list[str]) -> list[Tuple[bool, float]]:
        """Verify multiple images in batch."""
        return [self.verify(p) for p in image_paths]
