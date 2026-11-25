from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Path, UploadFile
from fastapi.responses import FileResponse

from app.api.dependencies import (
    BlankFormFieldDetectorDependency,
    SettingsDependency,
    TemplateStoreDependency,
    read_upload,
)
from app.imaging.page import load_page_images
from app.schemas import Template, TemplateCreate, TemplateDraft, TemplateSummary, TemplateUpdate
from app.services.form_processing import build_template_draft

router = APIRouter(prefix="/api/templates", tags=["templates"])

PageIndexPath = Annotated[int, Path(ge=0)]


@router.post("/drafts", response_model=TemplateDraft)
def create_template_draft(
    file: UploadFile,
    settings: SettingsDependency,
    store: TemplateStoreDependency,
    detector: BlankFormFieldDetectorDependency,
) -> TemplateDraft:
    content = read_upload(file, max_bytes=settings.max_upload_bytes)
    return build_template_draft(load_page_images(content), detector=detector, store=store)


@router.get("/drafts/{draft_id}/pages/{page_index}/image", response_class=FileResponse)
def get_draft_image(
    draft_id: str, page_index: PageIndexPath, store: TemplateStoreDependency
) -> FileResponse:
    return FileResponse(store.draft_image_path(draft_id, page_index), media_type="image/png")


@router.post("", response_model=Template, status_code=HTTPStatus.CREATED)
def create_template(request: TemplateCreate, store: TemplateStoreDependency) -> Template:
    return store.create(request)


@router.get("", response_model=list[TemplateSummary])
def list_templates(store: TemplateStoreDependency) -> list[TemplateSummary]:
    return store.list_summaries()


@router.get("/{template_id}", response_model=Template)
def get_template(template_id: str, store: TemplateStoreDependency) -> Template:
    return store.get(template_id)


@router.put("/{template_id}", response_model=Template)
def update_template(
    template_id: str, request: TemplateUpdate, store: TemplateStoreDependency
) -> Template:
    return store.update(template_id, request)


@router.delete("/{template_id}", status_code=HTTPStatus.NO_CONTENT)
def delete_template(template_id: str, store: TemplateStoreDependency) -> None:
    store.delete(template_id)


@router.get("/{template_id}/pages/{page_index}/image", response_class=FileResponse)
def get_template_image(
    template_id: str, page_index: PageIndexPath, store: TemplateStoreDependency
) -> FileResponse:
    return FileResponse(store.image_path(template_id, page_index), media_type="image/png")
