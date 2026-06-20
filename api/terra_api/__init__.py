"""Terra OBIA HTTP API.

FastAPI service that exposes the core OBIA engine over REST. The API layer
handles request validation, job status, and authentication (future); it does not
embed geospatial processing logic directly.
"""

__version__ = "0.1.0"
