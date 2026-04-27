"""
Project Astra - Reference Manager
Manages 5 canonical reference images per persona with LoRA-ready directory structure.
"""

import os
import shutil
from pathlib import Path
from typing import List, Optional, Tuple

from src.utils.logger import logger


class ReferenceManager:
    """
    Handles canonical reference images for persona consistency.
    Directory layout: data/{persona_id}/reference/canonical_1..5.png
    """

    CANONICAL_COUNT: int = 5
    ACCEPTED_FORMATS: Tuple[str, ...] = (".png", ".jpg", ".jpeg", ".webp")

    def __init__(self, persona_id: str = "astra") -> None:
        self.persona_id = persona_id
        self.reference_dir = Path(f"data/{persona_id}/reference")
        self.reference_dir.mkdir(parents=True, exist_ok=True)

    def get_canonical_paths(self) -> List[Path]:
        """Return paths to all canonical reference images."""
        paths: List[Path] = []
        for i in range(1, self.CANONICAL_COUNT + 1):
            for ext in self.ACCEPTED_FORMATS:
                candidate = self.reference_dir / f"canonical_{i}{ext}"
                if candidate.exists():
                    paths.append(candidate)
                    break
        return paths

    def all_canonicals_exist(self) -> bool:
        """Check if all 5 canonical images are present."""
        return len(self.get_canonical_paths()) == self.CANONICAL_COUNT

    def store_candidate(self, source_path: str, index: int) -> Path:
        """
        Store a candidate image as a canonical reference.
        Args:
            source_path: Path to the source image.
            index: Canonical index (1-5).
        Returns:
            Path to the stored canonical image.
        """
        if not (1 <= index <= self.CANONICAL_COUNT):
            raise ValueError(f"Index must be between 1 and {self.CANONICAL_COUNT}")

        src = Path(source_path)
        if not src.exists():
            raise FileNotFoundError(f"Source image not found: {source_path}")

        dest = self.reference_dir / f"canonical_{index}.png"
        shutil.copy2(str(src), str(dest))
        logger.info(f"Stored canonical_{index} for persona '{self.persona_id}': {dest}")
        return dest

    def inject_reference_context(self, prompt: str) -> str:
        """
        Append reference image descriptions to a generation prompt.
        This helps maintain persona consistency across generated content.
        """
        canonicals = self.get_canonical_paths()
        if not canonicals:
            return prompt

        # Build a compact reference descriptor
        descriptor = (
            " Maintain exact same person: honey blonde mid-length wavy hair, "
            "hazel eyes with distinct upper-right catchlight, natural flawless skin "
            "with visible pores, slight realistic facial asymmetry, athletic Pilates-oriented physique, "
            "warm undertones, subtle freckles across nose bridge, minimalist silver pendant necklace."
        )
        return f"{prompt}{descriptor}"

    def get_lora_ready_dir(self) -> Path:
        """Return the LoRA training directory for this persona."""
        lora_dir = Path(f"data/{self.persona_id}/lora_training")
        lora_dir.mkdir(parents=True, exist_ok=True)
        return lora_dir

    def prepare_lora_dataset(self) -> List[Path]:
        """
        Copy canonical images into the LoRA training directory.
        Returns paths in the LoRA directory.
        """
        lora_dir = self.get_lora_ready_dir()
        canonicals = self.get_canonical_paths()
        copied: List[Path] = []
        for idx, src in enumerate(canonicals, start=1):
            dest = lora_dir / f"{self.persona_id}_{idx}.png"
            shutil.copy2(str(src), str(dest))
            copied.append(dest)
        logger.info(f"Prepared {len(copied)} images for LoRA training in {lora_dir}")
        return copied
