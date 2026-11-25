from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

FIELD_KEY_PATTERN = r"^[a-z][a-z0-9_]*$"
FIELD_KEY_MAX_LENGTH = 64
FIELD_LABEL_MAX_LENGTH = 200
TEMPLATE_NAME_MAX_LENGTH = 120


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class BoundingBox(CamelModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height


class FieldType(StrEnum):
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    CHOICE = "choice"


class PageSize(CamelModel):
    image_width: int
    image_height: int


class ChoiceOption(CamelModel):
    id: str = Field(min_length=1, max_length=64)
    label: str = Field(max_length=FIELD_LABEL_MAX_LENGTH)
    box: BoundingBox


class TemplateField(CamelModel):
    id: str = Field(min_length=1, max_length=64)
    key: str = Field(pattern=FIELD_KEY_PATTERN, max_length=FIELD_KEY_MAX_LENGTH)
    label: str = Field(max_length=FIELD_LABEL_MAX_LENGTH)
    field_type: FieldType
    page_index: int = Field(ge=0)
    box: BoundingBox
    options: list[ChoiceOption] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_options_only_for_choices(self) -> "TemplateField":
        is_choice = self.field_type is FieldType.CHOICE
        if is_choice and not self.options:
            raise ValueError("A choice field needs at least one option")
        if not is_choice and self.options:
            raise ValueError("Only choice fields can have options")
        return self


class TemplateFieldsInput(CamelModel):
    name: str = Field(min_length=1, max_length=TEMPLATE_NAME_MAX_LENGTH)
    fields: list[TemplateField]

    @model_validator(mode="after")
    def require_unique_keys(self) -> "TemplateFieldsInput":
        keys = [field.key for field in self.fields]
        if len(keys) != len(set(keys)):
            raise ValueError("Field keys must be unique")
        return self


class TemplateCreate(TemplateFieldsInput):
    draft_id: str


class TemplateUpdate(TemplateFieldsInput):
    pass


class TemplateDraft(CamelModel):
    draft_id: str
    pages: list[PageSize]
    fields: list[TemplateField]


class Template(CamelModel):
    id: str
    name: str
    pages: list[PageSize]
    fields: list[TemplateField]
    created_at: datetime
    updated_at: datetime


class TemplateSummary(CamelModel):
    id: str
    name: str
    field_count: int
    updated_at: datetime


class FieldStatus(StrEnum):
    CONFIRMED = "confirmed"
    REVIEW = "review"
    EMPTY = "empty"


class EngineReading(CamelModel):
    engine: str
    text: str
    confidence: float


class ExtractedField(CamelModel):
    field_id: str
    key: str
    label: str
    field_type: FieldType
    page_index: int
    box: BoundingBox
    value: str
    confidence: float
    status: FieldStatus
    readings: list[EngineReading]


class ResultPage(CamelModel):
    page_index: int
    scan_page_number: int
    image_data_url: str
    image_width: int
    image_height: int
    is_aligned: bool


class ExtractionResult(CamelModel):
    template_id: str
    template_name: str
    pages: list[ResultPage]
    values: dict[str, str]
    fields: list[ExtractedField]


class EngineAvailability(CamelModel):
    model: str
    is_available: bool


class HealthStatus(CamelModel):
    is_ollama_reachable: bool
    fast_model: EngineAvailability
    accurate_model: EngineAvailability


class ErrorResponse(CamelModel):
    code: str
    message: str
    page_numbers: list[int] | None = None
