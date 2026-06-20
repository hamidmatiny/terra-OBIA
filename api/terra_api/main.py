"""FastAPI application factory and route registration."""

from fastapi import FastAPI

from terra_api.config import settings
from terra_api.routes import health, jobs


def create_app() -> FastAPI:
    """Build and configure the FastAPI application instance."""
    app = FastAPI(
        title="Terra OBIA API",
        description="REST API for Object-Based Image Analysis workflows",
        version="0.1.0",
    )
    app.include_router(health.router, tags=["health"])
    app.include_router(jobs.router, prefix="/v1/jobs", tags=["jobs"])
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
