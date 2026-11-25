from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OCR_", env_file=BACKEND_ROOT / ".env")

    data_dir: Path = BACKEND_ROOT / "data"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    max_upload_bytes: int = 20 * 1024 * 1024

    ollama_url: str = "http://localhost:11434"
    ollama_timeout_seconds: float = 120.0
    ollama_keep_alive: str = "30m"
    fast_model: str = "qwen3-vl:4b"
    accurate_model: str = "qwen3-vl:8b"
    skip_model_thinking: bool = True

    confidence_threshold: float = 0.85


@lru_cache
def get_settings() -> Settings:
    return Settings()
