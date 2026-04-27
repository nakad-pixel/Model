"""
Project Astra - Reference Management Package
Persona consistency via canonical images, embeddings, and perceptual hashes.
"""

from src.reference.reference_manager import ReferenceManager
from src.reference.embedding_generator import EmbeddingGenerator
from src.reference.face_verifier import FaceVerifier
from src.reference.hash_store import HashStore

__all__ = [
    "ReferenceManager",
    "EmbeddingGenerator",
    "FaceVerifier",
    "HashStore",
]
