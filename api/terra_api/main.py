"""FastAPI application factory and route registration."""

from __future__ import annotations

import logging

from fastapi import FastAPI

from terra_api.config import settings
from terra_api.middleware import RequestLoggingMiddleware
from terra_api.routes import health, jobs, models


def create_app() -> FastAPI:
    """Build and configure the FastAPI application instance."""
    logging.basicConfig(level=settings.log_level)

    app = FastAPI(
        title="Terra OBIA API",
        description=(
            "Professional REST API for Object-Based Image Analysis workflows — "
            "automated forest stand delineation, segmentation, classification, "
            "and GIS export for government and enterprise forestry customers."
        ),
        version="0.2.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_tags=[
            {
                "name": "jobs",
                "description": "Submit and monitor province-scale OBIA processing jobs.",
            },
            {
                "name": "models",
                "description": "Browse trained classification models and accuracy reports.",
            },
            {
                "name": "health",
                "description": "Service health checks.",
            },
        ],
    )
    app.add_middleware(RequestLoggingMiddleware)
    app.include_router(health.router, tags=["health"])
    app.include_router(jobs.router, prefix="/v1/jobs", tags=["jobs"])
    app.include_router(models.router, prefix="/v1/models", tags=["models"])
    return app


app = create_app()


def run() -> None:
    """Entry point for the ``terra-api`` console script."""
    import uvicorn

    uvicorn.run(
        "terra_api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.env == "development",
    )
