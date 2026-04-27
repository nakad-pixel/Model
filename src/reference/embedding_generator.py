"""
Project Astra - Embedding Generator
Generates face embeddings using face_recognition (dlib) and InsightFace (optional).
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from src.utils.logger import logger


class EmbeddingGenerator:
    """
    Generates and stores face embeddings for persona consistency verification.
    Uses face_recognition (dlib) as primary and InsightFace as secondary when available.
    """

    def __init__(self, persona_id: str = "astra") -> None:
        self.persona_id = persona_id
        self.embeddings_dir = Path(f"data/{persona_id}/embeddings")
        self.embeddings_dir.mkdir(parents=True, exist_ok=True)
        self._face_recognition_available = self._check_face_recognition()
        self._insightface_available = self._check_insightface()

    @staticmethod
    def _check_face_recognition() -> bool:
        try:
            import face_recognition  # noqa: F401
            return True
        except Exception:
            logger.warning("face_recognition not available. Install with: pip install face-recognition")
            return False

    @staticmethod
    def _check_insightface() -> bool:
        try:
            import insightface  # noqa: F401
            return True
        except Exception:
            logger.debug("insightface not available.")
            return False

    def generate_embeddings(self, image_paths: List[Path]) -> Dict[str, Any]:
        """
        Generate embeddings for a list of reference images.
        Returns dict with 'face_recognition' and 'insightface' keys.
        """
        results: Dict[str, Any] = {
            "face_recognition": [],
            "insightface": [],
            "persona_id": self.persona_id,
        }

        for img_path in image_paths:
            if self._face_recognition_available:
                emb = self._generate_dlib_embedding(img_path)
                if emb is not None:
                    results["face_recognition"].append(emb.tolist())

            if self._insightface_available:
                emb = self._generate_insightface_embedding(img_path)
                if emb is not None:
                    results["insightface"].append(emb.tolist())

        # Persist embeddings
        self._save_embeddings(results)
        logger.info(
            f"Generated embeddings for {self.persona_id}: "
            f"dlib={len(results['face_recognition'])}, insightface={len(results['insightface'])}"
        )
        return results

    def _generate_dlib_embedding(self, image_path: Path) -> Optional[np.ndarray]:
        """Generate 128-d dlib face encoding via face_recognition."""
        try:
            import face_recognition

            img = face_recognition.load_image_file(str(image_path))
            encodings = face_recognition.face_encodings(img)
            if encodings:
                return encodings[0]
            logger.warning(f"No face detected in {image_path} (dlib)")
            return None
        except Exception as exc:
            logger.error(f"dlib embedding failed for {image_path}: {exc}")
            return None

    def _generate_insightface_embedding(self, image_path: Path) -> Optional[np.ndarray]:
        """Generate InsightFace embedding."""
        try:
            import insightface
            from insightface.app import FaceAnalysis

            app = FaceAnalysis(name="buffalo_l", root=str(self.embeddings_dir / ".insightface"))
            app.prepare(ctx_id=-1, det_size=(640, 640))

            img = np.array(Image.open(image_path).convert("RGB"))
            faces = app.get(img)
            if faces:
                return faces[0].embedding
            logger.warning(f"No face detected in {image_path} (InsightFace)")
            return None
        except Exception as exc:
            logger.error(f"InsightFace embedding failed for {image_path}: {exc}")
            return None

    def _save_embeddings(self, results: Dict[str, Any]) -> None:
        """Persist embeddings as .npy files."""
        import json

        meta_path = self.embeddings_dir / "embeddings.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        # Also save individual numpy arrays for fast loading
        if results["face_recognition"]:
            face_emb = np.array(results["face_recognition"])
            np.save(self.embeddings_dir / "face_embedding.npy", face_emb)

        if results["insightface"]:
            body_emb = np.array(results["insightface"])
            np.save(self.embeddings_dir / "body_embedding.npy", body_emb)

    def load_embeddings(self) -> Dict[str, Any]:
        """Load previously generated embeddings."""
        import json

        meta_path = self.embeddings_dir / "embeddings.json"
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"face_recognition": [], "insightface": [], "persona_id": self.persona_id}

    def get_mean_embedding(self, backend: str = "face_recognition") -> Optional[np.ndarray]:
        """
        Compute mean embedding vector for the given backend.
        Useful for quick similarity checks.
        """
        data = self.load_embeddings()
        vectors = data.get(backend, [])
        if not vectors:
            return None
        return np.mean(np.array(vectors), axis=0)
