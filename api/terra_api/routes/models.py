"""Trained classification model listing endpoints."""

from fastapi import APIRouter

from terra_api.auth import AuthenticatedKey
from terra_api.schemas import ModelListResponse
from terra_api.services.model_registry import list_available_models

router = APIRouter()


@router.get(
    "",
    response_model=ModelListResponse,
    summary="List trained classification models",
    description=(
        "Returns versioned stand delineation models with training metadata and "
        "validation accuracy suitable for audit and model selection."
    ),
)
def list_models(_: AuthenticatedKey) -> ModelListResponse:
    """List available trained models and their accuracy summaries."""
    return list_available_models()
