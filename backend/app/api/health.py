from fastapi import APIRouter

from app.api.dependencies import OllamaClientDependency, SettingsDependency
from app.ocr.qwen_engine import list_available_models
from app.schemas import EngineAvailability, HealthStatus

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("", response_model=HealthStatus)
def get_health(settings: SettingsDependency, client: OllamaClientDependency) -> HealthStatus:
    available_models = list_available_models(client)
    installed = available_models or set()
    return HealthStatus(
        is_ollama_reachable=available_models is not None,
        fast_model=EngineAvailability(
            model=settings.fast_model, is_available=settings.fast_model in installed
        ),
        accurate_model=EngineAvailability(
            model=settings.accurate_model, is_available=settings.accurate_model in installed
        ),
    )
