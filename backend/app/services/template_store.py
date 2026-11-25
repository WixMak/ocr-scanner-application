import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np

from app.errors import DraftNotFoundError, FieldOutsideImageError, TemplateNotFoundError
from app.imaging.page import encode_png, is_box_within
from app.schemas import (
    PageSize,
    Template,
    TemplateCreate,
    TemplateField,
    TemplateSummary,
    TemplateUpdate,
)

STORED_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


class TemplateStore:
    """Keeps templates as JSON + one blank-form PNG per page. Filled-in scans are never stored."""

    def __init__(self, data_dir: Path) -> None:
        self._templates_dir = data_dir / "templates"
        self._drafts_dir = data_dir / "drafts"
        self._templates_dir.mkdir(parents=True, exist_ok=True)
        self._drafts_dir.mkdir(parents=True, exist_ok=True)

    def save_draft_images(self, page_images: list[np.ndarray]) -> str:
        draft_id = uuid4().hex
        for page_index, image in enumerate(page_images):
            self._draft_page_path(draft_id, page_index).write_bytes(encode_png(image))
        return draft_id

    def draft_image_path(self, draft_id: str, page_index: int) -> Path:
        path = self._draft_page_path(draft_id, page_index)
        if not STORED_ID_PATTERN.match(draft_id) or not path.exists():
            raise DraftNotFoundError()
        return path

    def create(self, request: TemplateCreate) -> Template:
        draft_paths = self._draft_page_paths(request.draft_id)
        pages = [_read_page_size(path) for path in draft_paths]
        _ensure_fields_within(request.fields, pages)
        now = datetime.now(UTC)
        template = Template(
            id=uuid4().hex,
            name=request.name,
            pages=pages,
            fields=request.fields,
            created_at=now,
            updated_at=now,
        )
        for page_index, draft_path in enumerate(draft_paths):
            draft_path.rename(self._image_path(template.id, page_index))
        self._write(template)
        return template

    def update(self, template_id: str, request: TemplateUpdate) -> Template:
        existing = self.get(template_id)
        _ensure_fields_within(request.fields, existing.pages)
        updated = existing.model_copy(
            update={
                "name": request.name,
                "fields": request.fields,
                "updated_at": datetime.now(UTC),
            }
        )
        self._write(updated)
        return updated

    def get(self, template_id: str) -> Template:
        path = self._json_path(template_id)
        if not path.exists():
            raise TemplateNotFoundError()
        return Template.model_validate_json(path.read_text(encoding="utf-8"))

    def list_summaries(self) -> list[TemplateSummary]:
        templates = [
            Template.model_validate_json(path.read_text(encoding="utf-8"))
            for path in self._templates_dir.glob("*.json")
        ]
        templates.sort(key=lambda template: template.updated_at, reverse=True)
        return [
            TemplateSummary(
                id=template.id,
                name=template.name,
                field_count=len(template.fields),
                updated_at=template.updated_at,
            )
            for template in templates
        ]

    def delete(self, template_id: str) -> None:
        template = self.get(template_id)
        self._json_path(template_id).unlink()
        for page_index in range(len(template.pages)):
            self._image_path(template_id, page_index).unlink(missing_ok=True)

    def image_path(self, template_id: str, page_index: int) -> Path:
        path = self._image_path(template_id, page_index)
        if not path.exists():
            raise TemplateNotFoundError()
        return path

    def load_blank_pages(self, template: Template) -> list[np.ndarray]:
        return [
            self._load_image(template.id, page_index) for page_index in range(len(template.pages))
        ]

    def _load_image(self, template_id: str, page_index: int) -> np.ndarray:
        image = cv2.imread(str(self.image_path(template_id, page_index)), cv2.IMREAD_COLOR)
        if image is None:
            raise TemplateNotFoundError()
        return image

    def _draft_page_paths(self, draft_id: str) -> list[Path]:
        paths = [self.draft_image_path(draft_id, 0)]
        next_path = self._draft_page_path(draft_id, 1)
        while next_path.exists():
            paths.append(next_path)
            next_path = self._draft_page_path(draft_id, len(paths))
        return paths

    def _write(self, template: Template) -> None:
        self._json_path(template.id).write_text(
            template.model_dump_json(by_alias=True, indent=2), encoding="utf-8"
        )

    def _json_path(self, template_id: str) -> Path:
        _ensure_valid_template_id(template_id)
        return self._templates_dir / f"{template_id}.json"

    def _image_path(self, template_id: str, page_index: int) -> Path:
        _ensure_valid_template_id(template_id)
        return self._templates_dir / f"{template_id}-{page_index}.png"

    def _draft_page_path(self, draft_id: str, page_index: int) -> Path:
        return self._drafts_dir / f"{draft_id}-{page_index}.png"


def _ensure_valid_template_id(template_id: str) -> None:
    if not STORED_ID_PATTERN.match(template_id):
        raise TemplateNotFoundError()


def _ensure_fields_within(fields: list[TemplateField], pages: list[PageSize]) -> None:
    for field in fields:
        if not _is_on_its_page(field, pages):
            raise FieldOutsideImageError(field.key)


def _is_on_its_page(field: TemplateField, pages: list[PageSize]) -> bool:
    if field.page_index >= len(pages):
        return False
    page = pages[field.page_index]
    boxes = [field.box, *(option.box for option in field.options)]
    return all(
        is_box_within(box, width=page.image_width, height=page.image_height) for box in boxes
    )


def _read_page_size(path: Path) -> PageSize:
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise DraftNotFoundError()
    height, width = image.shape[:2]
    return PageSize(image_width=width, image_height=height)
