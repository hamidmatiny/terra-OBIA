"""Deep-learning segmentation using a pretrained FCN-ResNet50 backbone."""

from __future__ import annotations

import logging

import numpy as np
import torch
from numpy.typing import NDArray
from rasterio.transform import Affine
from skimage.segmentation import relabel_sequential
from torchvision.models.segmentation import fcn_resnet50

from terra_core.segmentation.base import SegmentationModel
from terra_core.segmentation.config import SegmentationConfig
from terra_core.segmentation.models import TileSegmentationResult
from terra_core.segmentation.reproducibility import log_segmentation_run
from terra_core.segmentation.vectorize import vectorize_labels

logger = logging.getLogger("terra_core.segmentation")


def _to_rgb_tensor(data: NDArray[np.floating]) -> torch.Tensor:
    """Convert tile data to normalized RGB tensor for FCN inference.

    Expected CRS/resolution assumptions:
        - First three bands are treated as RGB proxies for multispectral input
          until forestry fine-tuning is available.
    """
    bands, height, width = data.shape
    if bands >= 3:
        rgb = data[:3]
    elif bands == 2:
        rgb = np.stack([data[0], data[1], data[1]], axis=0)
    else:
        rgb = np.repeat(data[:1], 3, axis=0)

    rgb = rgb.astype(np.float32)
    lower = float(np.nanmin(rgb))
    upper = float(np.nanmax(rgb))
    if upper > lower:
        rgb = (rgb - lower) / (upper - lower)

    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)[:, None, None]
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)[:, None, None]
    rgb = (rgb - mean) / std
    return torch.from_numpy(rgb).unsqueeze(0)


class DeepSegmenter(SegmentationModel):
    """Pretrained FCN-ResNet50 segmenter (primary learned path).

    Expected CRS/resolution assumptions:
        - Requires at least one spectral band; first three bands are mapped to
          RGB for the ImageNet-pretrained encoder.
        - Outputs semantic labels at input resolution (native GSD).
        - Fine-tuning on NB DNRED forestry imagery is planned; current weights
          are COCO-pretrained and serve as a functional DL baseline.

    Note:
        Segment Anything Model (SAM) support is planned as an alternative backend
        implementing the same ``SegmentationModel`` interface.
    """

    def __init__(
        self,
        config: SegmentationConfig,
        *,
        pretrained: bool = True,
        device: str | None = None,
    ) -> None:
        """Load FCN weights and select compute device."""
        super().__init__(config)
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        weights = "DEFAULT" if pretrained else None
        self.model = fcn_resnet50(weights=weights)
        self.model.eval()
        self.model.to(self.device)

    def segment_tile(
        self,
        data: NDArray[np.floating],
        *,
        tile_id: str,
        tile_row: int,
        tile_col: int,
        col_off: int,
        row_off: int,
        transform: Affine,
        nodata: float | None = None,
    ) -> TileSegmentationResult:
        """Run FCN inference on one tile and vectorize confident objects."""
        tensor = _to_rgb_tensor(np.asarray(data, dtype=np.float64)).to(self.device)
        with torch.inference_mode():
            output = self.model(tensor)["out"]
            probabilities = torch.softmax(output, dim=1)
            max_prob, labels = torch.max(probabilities, dim=1)

        labels_np = labels.squeeze(0).cpu().numpy().astype(np.int32)
        max_prob_np = max_prob.squeeze(0).cpu().numpy()
        labels_np[max_prob_np < self.config.confidence_threshold] = 0

        if nodata is not None:
            nodata_mask = np.any(data == nodata, axis=0)
            labels_np[nodata_mask] = 0

        # Relabel contiguous regions to unique object IDs starting at 1.
        labels_np, _, _ = relabel_sequential(labels_np, offset=1)  # type: ignore[no-untyped-call]

        objects = vectorize_labels(
            labels_np,
            np.asarray(data, dtype=np.float64),
            transform,
            crs_wkt=None,
            band_names=self.config.band_names,
            min_object_area_px=self.config.min_object_area_px,
        )
        snapshot = self.config_snapshot
        snapshot["pretrained"] = True
        snapshot["model"] = "fcn_resnet50"
        log_segmentation_run(logger, tile_id=tile_id, config=snapshot, backend="deep")
        return TileSegmentationResult(
            tile_id=tile_id,
            tile_row=tile_row,
            tile_col=tile_col,
            col_off=col_off,
            row_off=row_off,
            label_raster=labels_np,
            objects=objects,
            transform=transform,
            config_snapshot=snapshot,
        )
