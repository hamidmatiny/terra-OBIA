"""Configurable segmentation parameters for reproducible OBIA jobs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class SegmentationBackend(str, Enum):
    """Supported segmentation backend identifiers."""

    CLASSICAL = "classical"
    DEEP = "deep"


@dataclass(frozen=True)
class SegmentationConfig:
    """Job-level segmentation parameters logged with every result.

    Expected input assumptions:
        - Classical SLIC uses the first 3 bands (or repeated single band) as
          RGB-like input at native resolution.
        - Deep FCN expects at least 3 bands mapped to RGB ordering; additional
          bands are ignored by the pretrained encoder until fine-tuning lands.

    Attributes:
        backend: ``classical`` (SLIC) or ``deep`` (FCN-ResNet50).
        n_segments: Target number of superpixels for SLIC (scale proxy).
        compactness: SLIC compactness (higher → more square superpixels).
        sigma: Gaussian smoothing sigma applied before SLIC.
        confidence_threshold: Minimum softmax probability for deep labels.
        min_object_area_px: Minimum object area in pixels after vectorization.
    """

    backend: SegmentationBackend = SegmentationBackend.DEEP
    n_segments: int = 250
    compactness: float = 10.0
    sigma: float = 1.0
    confidence_threshold: float = 0.5
    min_object_area_px: int = 16
    band_names: tuple[str, ...] = ("band_1", "band_2", "band_3")

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-serializable parameter record for audit trails."""
        data = asdict(self)
        data["backend"] = self.backend.value
        return data

    @classmethod
    def classical(
        cls,
        *,
        n_segments: int = 250,
        compactness: float = 10.0,
        sigma: float = 1.0,
    ) -> SegmentationConfig:
        """Build a classical SLIC configuration."""
        return cls(
            backend=SegmentationBackend.CLASSICAL,
            n_segments=n_segments,
            compactness=compactness,
            sigma=sigma,
        )

    @classmethod
    def deep(cls, *, confidence_threshold: float = 0.5) -> SegmentationConfig:
        """Build a deep-learning FCN configuration."""
        return cls(
            backend=SegmentationBackend.DEEP,
            confidence_threshold=confidence_threshold,
        )
