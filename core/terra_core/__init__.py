"""Terra OBIA core engine.

This package provides the foundational OBIA capabilities: geospatial I/O,
segmentation, and classification. It is intentionally decoupled from ingestion
pipelines, API transport, and export workflows so that downstream products
(e.g. wetland classification, carbon MRV) can reuse the same engine.
"""

__version__ = "0.1.0"
