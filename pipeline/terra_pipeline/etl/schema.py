"""FO/WL/NF inventory schema and field-name detection patterns."""

from __future__ import annotations

from typing import Final

INVENTORY_CLASSES: Final[tuple[str, ...]] = ("FO", "WL", "NF", "WA")
FOREST_SUBTYPES: Final[tuple[str, ...]] = ("conifer", "deciduous", "mixed")
CANOPY_CLASSES: Final[tuple[str, ...]] = ("open", "sparse", "moderate", "dense")

INVENTORY_FIELD_PATTERNS: Final[tuple[str, ...]] = (
    "inventory_class",
    "inv_class",
    "lc_class",
    "landcover",
    "land_cover",
    "fo_wl_nf",
    "class_code",
    "veg_class",
)

COVER_TYPE_FIELD_PATTERNS: Final[tuple[str, ...]] = (
    "cover_type",
    "dom_cover",
    "dominant_cover",
    "fotype",
    "forest_type",
    "species_group",
)

CANOPY_FIELD_PATTERNS: Final[tuple[str, ...]] = (
    "canopy_closure_class",
    "canopy_class",
    "closure_class",
    "crown_closure",
    "canopy_closure",
)

# Normalized inventory codes from common government aliases.
INVENTORY_ALIASES: Final[dict[str, str]] = {
    "FO": "FO",
    "FOREST": "FO",
    "FOR": "FO",
    "WL": "WL",
    "WETLAND": "WL",
    "WET": "WL",
    "NF": "NF",
    "NONFOREST": "NF",
    "NON_FOREST": "NF",
    "NON-FOR": "NF",
    "OPEN": "NF",
    "WA": "WA",
    "WATER": "WA",
    "LAKE": "WA",
    "RIVER": "WA",
}

RASTER_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {".tif", ".tiff", ".geotiff", ".jp2", ".j2k", ".img"}
)
VECTOR_EXTENSIONS: Final[frozenset[str]] = frozenset({".shp", ".gpkg", ".geojson", ".json", ".csv"})
ARCHIVE_EXTENSIONS: Final[frozenset[str]] = frozenset({".zip"})

BAND_NAMES_RGBN: Final[tuple[str, ...]] = ("band_1", "band_2", "band_3", "band_4")
