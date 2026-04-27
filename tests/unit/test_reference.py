"""
Unit Tests: Reference Management, Embeddings, Face Verification, Hash Store
"""

import os
import tempfile
from pathlib import Path

import pytest
from PIL import Image

from src.reference.embedding_generator import EmbeddingGenerator
from src.reference.face_verifier import FaceVerifier
from src.reference.hash_store import HashStore
from src.reference.reference_manager import ReferenceManager


class TestReferenceManager:
    """Tests for canonical reference image management."""

    def test_canonical_paths_empty(self):
        """Empty reference directory should return empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original = os.getcwd()
            os.chdir(tmpdir)
            try:
                mgr = ReferenceManager(persona_id="test_empty")
                mgr.reference_dir = Path(tmpdir)
                assert mgr.get_canonical_paths() == []
                assert mgr.all_canonicals_exist() is False
            finally:
                os.chdir(original)

    def test_store_candidate_and_retrieve(self):
        """Store a candidate and verify retrieval."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original = os.getcwd()
            os.chdir(tmpdir)
            try:
                mgr = ReferenceManager(persona_id="test_store")
                mgr.reference_dir = Path(tmpdir)

                src = Path(tmpdir) / "source.png"
                Image.new("RGB", (100, 200), color="red").save(src)

                dest = mgr.store_candidate(str(src), 1)
                assert dest.exists()
                assert dest.name == "canonical_1.png"
            finally:
                os.chdir(original)

    def test_inject_reference_context(self):
        """Prompt should be augmented with reference descriptor when canonicals exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original = os.getcwd()
            os.chdir(tmpdir)
            try:
                mgr = ReferenceManager(persona_id="test_prompt")
                mgr.reference_dir = Path(tmpdir)
                # Create a fake canonical so descriptor is injected
                src = Path(tmpdir) / "source_1.png"
                Image.new("RGB", (100, 200), color="blue").save(src)
                mgr.store_candidate(str(src), 1)

                prompt = "A person standing in a garden"
                result = mgr.inject_reference_context(prompt)
                assert prompt in result
                assert "honey blonde" in result.lower()
            finally:
                os.chdir(original)

    def test_lora_dir_creation(self):
        """LoRA directory should be created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original = os.getcwd()
            os.chdir(tmpdir)
            try:
                mgr = ReferenceManager(persona_id="test_lora")
                mgr.reference_dir = Path(tmpdir)
                lora_dir = mgr.get_lora_ready_dir()
                assert lora_dir.exists()
            finally:
                os.chdir(original)


class TestHashStore:
    """Tests for perceptual hash drift detection."""

    def test_compute_phash(self):
        """pHash computation should return consistent string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original = os.getcwd()
            os.chdir(tmpdir)
            try:
                img_path = Path(tmpdir) / "test.png"
                Image.new("RGB", (100, 200), color="blue").save(img_path)

                store = HashStore(persona_id="test_hash")
                store.hash_dir = Path(tmpdir)
                store.store_path = Path(tmpdir) / "hashes.json"
                phash = store.compute_phash(str(img_path))
                assert phash is not None
                assert len(phash) > 0
            finally:
                os.chdir(original)

    def test_check_drift_with_reference(self):
        """Identical image should have zero drift."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original = os.getcwd()
            os.chdir(tmpdir)
            try:
                img_path = Path(tmpdir) / "ref.png"
                Image.new("RGB", (200, 300), color="green").save(img_path)

                store = HashStore(persona_id="test_drift")
                store.hash_dir = Path(tmpdir)
                store.store_path = Path(tmpdir) / "hashes.json"
                store.add_reference_hashes([img_path])

                ok, dist = store.check_drift(str(img_path))
                assert bool(ok) is True
                assert dist == 0
            finally:
                os.chdir(original)

    def test_accept_and_reject(self):
        """Accepted and rejected images should be recorded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original = os.getcwd()
            os.chdir(tmpdir)
            try:
                img_path = Path(tmpdir) / "img.png"
                Image.new("RGB", (200, 300), color="purple").save(img_path)

                store = HashStore(persona_id="test_acc")
                store.hash_dir = Path(tmpdir)
                store.store_path = Path(tmpdir) / "hashes.json"
                store.accept_image(str(img_path))
                store.reject_image(str(img_path), reason="test")

                report = store.get_drift_report()
                assert report["accepted_count"] >= 1
                assert report["rejected_count"] >= 1
            finally:
                os.chdir(original)


class TestEmbeddingGenerator:
    """Tests for embedding generation (graceful when libs unavailable)."""

    def test_load_embeddings_empty(self):
        """Loading embeddings with no file returns empty defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original = os.getcwd()
            os.chdir(tmpdir)
            try:
                gen = EmbeddingGenerator(persona_id="test_emb")
                gen.embeddings_dir = Path(tmpdir)
                data = gen.load_embeddings()
                assert data["face_recognition"] == []
                assert data["insightface"] == []
            finally:
                os.chdir(original)

    def test_mean_embedding_none(self):
        """Mean embedding should be None when no data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original = os.getcwd()
            os.chdir(tmpdir)
            try:
                gen = EmbeddingGenerator(persona_id="test_mean")
                gen.embeddings_dir = Path(tmpdir)
                assert gen.get_mean_embedding("face_recognition") is None
            finally:
                os.chdir(original)


class TestFaceVerifier:
    """Tests for face verification (graceful when libs unavailable)."""

    def test_verify_missing_file(self):
        """Missing file should return False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original = os.getcwd()
            os.chdir(tmpdir)
            try:
                verifier = FaceVerifier(persona_id="test_ver")
                verifier.embedding_generator.embeddings_dir = Path(tmpdir)
                ok, score = verifier.verify("/tmp/nonexistent_file_12345.png")
                assert ok is False
                assert score == 0.0
            finally:
                os.chdir(original)

    def test_cosine_similarity(self):
        """Identical vectors should have similarity 1.0."""
        import numpy as np

        a = np.array([1.0, 0.0, 0.0])
        b = np.array([1.0, 0.0, 0.0])
        assert FaceVerifier._cosine_similarity(a, b) == pytest.approx(1.0)

        c = np.array([0.0, 1.0, 0.0])
        assert FaceVerifier._cosine_similarity(a, c) == pytest.approx(0.0)
