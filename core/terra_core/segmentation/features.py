"""Compute object-level spectral and shape metrics from label rasters."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray
from shapely.geometry import Polygon


def compactness(area: float, perimeter: float) -> float:
    """Compute isoperimetric compactness (1.0 = circle, lower = irregular).

    Args:
        area: Object area in square CRS units.
        perimeter: Object perimeter in CRS units.

    Returns:
        Compactness in [0, 1] when area > 0, else 0.0.
    """
    if area <= 0 or perimeter <= 0:
        return 0.0
    return float(4.0 * math.pi * area / (perimeter**2))


def spectral_stats_for_object(
    data: NDArray[np.floating],
    mask: NDArray[np.bool_],
    band_names: tuple[str, ...],
) -> tuple[dict[str, float], dict[str, float]]:
    """Compute per-band mean and standard deviation inside an object mask.

    Expected CRS/resolution assumptions:
        - ``data`` bands align with ``band_names`` at native GSD.

    Args:
        data: Array ``(bands, height, width)``.
        mask: Boolean mask ``(height, width)`` for one object.
        band_names: Names for each band in ``data``.

    Returns:
        Tuple of mean and std dicts keyed by band name.
    """
    means: dict[str, float] = {}
    stds: dict[str, float] = {}
    band_count = data.shape[0]
    for band_idx in range(band_count):
        name = band_names[band_idx] if band_idx < len(band_names) else f"band_{band_idx + 1}"
        values = data[band_idx][mask]
        if values.size == 0:
            means[name] = float("nan")
            stds[name] = float("nan")
        else:
            means[name] = float(np.mean(values))
            stds[name] = float(np.std(values))
    return means, stds


def shape_metrics(geometry: Polygon) -> tuple[float, float, float]:
    """Compute area, perimeter, and compactness from a polygon geometry.

    Expected CRS/resolution assumptions:
        - Geometry coordinates are in the source CRS (typically metres).

    Args:
        geometry: Object polygon in source CRS.

    Returns:
        Tuple of ``(area_m2, perimeter_m, compactness)``.
    """
    area = float(geometry.area)
    perimeter = float(geometry.length)
    return area, perimeter, compactness(area, perimeter)
