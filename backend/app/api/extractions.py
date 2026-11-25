from typing import Annotated

from fastapi import APIRouter, Form, UploadFile

from app.api.dependencies import (
    FieldValueReaderDependency,
    SettingsDependency,
    TemplateStoreDependency,
    read_upload,
)
from app.imaging.page import load_page_images
from app.schemas import ExtractionResult
from app.services.form_processing import extract_form_values

router = APIRouter(prefix="/api/extractions", tags=["extractions"])


@router.post("", response_model=ExtractionResult)
def create_extraction(
    file: UploadFile,
    template_id: Annotated[str, Form(alias="templateId")],
    settings: SettingsDependency,
    store: TemplateStoreDependency,
    reader: FieldValueReaderDependency,
) -> ExtractionResult:
    template = store.get(template_id)
    content = read_upload(file, max_bytes=settings.max_upload_bytes)
    return extract_form_values(
        load_page_images(content),
        template=template,
        blank_pages=store.load_blank_pages(template),
        reader=reader,
    )
