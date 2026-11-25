from functools import lru_cache
from typing import Annotated

import httpx
from fastapi import Depends, UploadFile

from app.config import Settings, get_settings
from app.errors import FileTooLargeError
from app.ocr.field_readers import LanguageRoutedFieldReader
from app.ocr.paddle_engine import PaddleOcrEngine
from app.ocr.qwen_engine import QwenVlEngine
from app.ocr.types import FieldValueReader
from app.services.field_detection import BlankFormFieldDetector, OpenCvFieldDetector
from app.services.template_store import TemplateStore

FAST_ENGINE_NAME = "qwen-fast"
ACCURATE_ENGINE_NAME = "qwen-accurate"

SettingsDependency = Annotated[Settings, Depends(get_settings)]


@lru_cache
def get_template_store() -> TemplateStore:
    return TemplateStore(get_settings().data_dir)


@lru_cache
def get_paddle_engine() -> PaddleOcrEngine:
    return PaddleOcrEngine()


@lru_cache
def get_ollama_client() -> httpx.Client:
    settings = get_settings()
    # trust_env=False: Ollama runs locally and must not be routed through a corporate proxy.
    return httpx.Client(
        base_url=settings.ollama_url, timeout=settings.ollama_timeout_seconds, trust_env=False
    )


def create_qwen_engine(*, name: str, model: str) -> QwenVlEngine:
    settings = get_settings()
    return QwenVlEngine(
        name=name,
        model=model,
        client=get_ollama_client(),
        keep_alive=settings.ollama_keep_alive,
        should_skip_thinking=settings.skip_model_thinking,
    )


def get_blank_form_field_detector() -> BlankFormFieldDetector:
    return OpenCvFieldDetector(label_reader=get_paddle_engine())


def get_field_value_reader() -> FieldValueReader:
    settings = get_settings()
    return LanguageRoutedFieldReader(
        layout_engine=get_paddle_engine(),
        fast_engine=create_qwen_engine(name=FAST_ENGINE_NAME, model=settings.fast_model),
        accurate_engine=create_qwen_engine(
            name=ACCURATE_ENGINE_NAME, model=settings.accurate_model
        ),
        confidence_threshold=settings.confidence_threshold,
    )


def read_upload(upload: UploadFile, *, max_bytes: int) -> bytes:
    content = upload.file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise FileTooLargeError(max_bytes)
    return content


TemplateStoreDependency = Annotated[TemplateStore, Depends(get_template_store)]
BlankFormFieldDetectorDependency = Annotated[
    BlankFormFieldDetector, Depends(get_blank_form_field_detector)
]
FieldValueReaderDependency = Annotated[FieldValueReader, Depends(get_field_value_reader)]
OllamaClientDependency = Annotated[httpx.Client, Depends(get_ollama_client)]
