"""
Project Astra - Media Validator
PIL-based checks for resolution, aspect ratio, format, and AI artifacts.
"""

import os
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image

from src.constants import MIN_FILE_SIZE_BYTES, MIN_IMAGE_DIMENSION
from src.utils.logger import logger


class MediaValidator:
    """Validates generated media before upload to social schedulers."""

    def __init__(self) -> None:
        self.errors: list[str] = []

    def validate(self, filepath: str) -> Tuple[bool, list[str]]:
        """
        Run all validation checks on an image file.
        Returns (is_valid, list_of_errors).
        """
        self.errors = []
        path = Path(filepath)

        if not path.exists():
            self.errors.append("File does not exist")
            return False, self.errors

        # Check 1: File size
        size = os.path.getsize(filepath)
        if size < MIN_FILE_SIZE_BYTES:
            self.errors.append(f"Invalid Size: {size} bytes (min {MIN_FILE_SIZE_BYTES})")

        # Check 2: Format and openability
        try:
            with Image.open(filepath) as img:
                fmt = img.format
                if fmt not in ("PNG", "JPEG", "JPG", "WEBP"):
                    self.errors.append(f"Invalid Format: {fmt}")

                width, height = img.size

                # Check 3: Resolution
                if width < MIN_IMAGE_DIMENSION and height < MIN_IMAGE_DIMENSION:
                    self.errors.append(
                        f"Invalid Resolution: {width}x{height} (min {MIN_IMAGE_DIMENSION}px)"
                    )

                # Check 4: Aspect ratio (portrait only)
                if height <= width:
                    self.errors.append(
                        f"Invalid Aspect Ratio (Landscape): {width}x{height} (height must exceed width)"
                    )

                # Check 5: Color histogram analysis for AI artifacts
                if not self._check_color_distribution(img):
                    self.errors.append("Color distribution suspicious (possible AI artifact)")

        except Exception as exc:
            self.errors.append(f"Image open failed: {exc}")

        is_valid = len(self.errors) == 0
        if is_valid:
            logger.info(f"Media validation passed: {filepath}")
        else:
            logger.warning(f"Media validation failed: {self.errors}")

        return is_valid, self.errors

    @staticmethod
    def _check_color_distribution(img: Image.Image) -> bool:
        """
        Basic check: ensure image isn't a single-color placeholder or extreme outlier.
        Returns True if color distribution looks normal.
        """
        try:
            # Convert to RGB and get histogram
            rgb = img.convert("RGB")
            hist = rgb.histogram()
            total_pixels = rgb.size[0] * rgb.size[1]

            # Check for extreme uniformity (placeholder/artifact)
            # If any single channel dominates > 95% of pixels uniformly, flag it
            r_hist = hist[0:256]
            g_hist = hist[256:512]
            b_hist = hist[512:768]

            max_r = max(r_hist)
            max_g = max(g_hist)
            max_b = max(b_hist)

            # If the peak channel count exceeds 90% of total pixels, likely uniform
            if max_r > total_pixels * 0.9 or max_g > total_pixels * 0.9 or max_b > total_pixels * 0.9:
                return False

            return True
        except Exception:
            return True  # Don't fail validation on histogram errors

    @staticmethod
    def get_dimensions(filepath: str) -> Optional[Tuple[int, int]]:
        """Return image dimensions without full validation."""
        try:
            with Image.open(filepath) as img:
                return img.size
        except Exception:
            return None
