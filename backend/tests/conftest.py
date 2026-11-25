from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_blank_form_field_detector,
    get_field_value_reader,
    get_ollama_client,
    get_template_store,
)
from app.imaging.page import NORMALISED_PAGE_WIDTH
from app.main import create_app
from app.ocr.types import FieldReading, Reading, TextLine
from app.schemas import BoundingBox, FieldStatus, FieldType
from app.services.field_detection import DetectedSlot
from app.services.template_store import TemplateStore

PAGE_HEIGHT = 1200
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

NAME_LABEL_BOX = BoundingBox(x=100, y=200, width=200, height=40)
NAME_UNDERLINE_Y = 240
NAME_UNDERLINE_LEFT = 320
NAME_UNDERLINE_RIGHT = 1200
NAME_ANSWER_BOX = BoundingBox(x=318, y=166, width=885, height=77)


def make_blank_form() -> np.ndarray:
    """A synthetic form: a title, a 'Name:' label with an underline, and textured anchors."""
    page = np.full((PAGE_HEIGHT, NORMALISED_PAGE_WIDTH, 3), 255, dtype=np.uint8)
    cv2.putText(page, "APPLICATION FORM", (100, 120), cv2.FONT_HERSHEY_SIMPLEX, 2, BLACK, 4)
    cv2.putText(page, "Name:", (100, 235), cv2.FONT_HERSHEY_SIMPLEX, 1.2, BLACK, 3)
    cv2.line(
        page,
        (NAME_UNDERLINE_LEFT, NAME_UNDERLINE_Y),
        (NAME_UNDERLINE_RIGHT, NAME_UNDERLINE_Y),
        BLACK,
        3,
    )
    for row in range(6):
        cv2.putText(
            page,
            f"SECTION {row} DETAILS AND NOTES {row * 7}",
            (100, 400 + row * 120),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.4,
            BLACK,
            3,
        )
    return page


PAGE_MARK_SIZE_PX = 38
PAGE_MARK_TOP_FROM_BOTTOM_PX = 100
LEFT_CORNER_MARK_X = 71
FIRST_NUMBER_MARK_X = 197
NUMBER_MARK_PITCH_PX = 63
RIGHT_CORNER_MARK_X = 1544


def add_page_marks(page: np.ndarray, page_number: int) -> np.ndarray:
    """Print the forms' page marks: a square in each bottom corner, one square per page number."""
    marked = page.copy()
    top = marked.shape[0] - PAGE_MARK_TOP_FROM_BOTTOM_PX
    number_mark_lefts = [
        FIRST_NUMBER_MARK_X + index * NUMBER_MARK_PITCH_PX for index in range(page_number)
    ]
    for left in [LEFT_CORNER_MARK_X, *number_mark_lefts, RIGHT_CORNER_MARK_X]:
        cv2.rectangle(
            marked, (left, top), (left + PAGE_MARK_SIZE_PX, top + PAGE_MARK_SIZE_PX), BLACK, -1
        )
    return marked


def write_on_form(page: np.ndarray, text: str) -> np.ndarray:
    filled = page.copy()
    cv2.putText(filled, text, (360, 228), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 1.4, (120, 40, 20), 3)
    return filled


def encode_image(image: np.ndarray, extension: str = ".png") -> bytes:
    is_encoded, buffer = cv2.imencode(extension, image)
    assert is_encoded
    return buffer.tobytes()


@dataclass
class FakeFieldDetector:
    slots: list[DetectedSlot]

    def detect_fields(self, image: np.ndarray) -> list[DetectedSlot]:
        return self.slots


@dataclass
class FakeCropReader:
    name: str
    text: str
    confidence: float
    call_count: int = 0

    def read(self, crop: np.ndarray) -> Reading:
        self.call_count += 1
        return Reading(engine=self.name, text=self.text, confidence=self.confidence)


@dataclass
class FakeFieldReader:
    value: str = "Chan Tai Man"
    confidence: float = 0.97
    status: FieldStatus = FieldStatus.CONFIRMED
    field_types: list[FieldType] = field(default_factory=list)
    crops: list[np.ndarray] = field(default_factory=list)

    def read_field(self, crop: np.ndarray, field_type: FieldType) -> FieldReading:
        self.field_types.append(field_type)
        self.crops.append(crop)
        return FieldReading(
            value=self.value,
            confidence=self.confidence,
            status=self.status,
            readings=[Reading(engine="fake", text=self.value, confidence=self.confidence)],
        )


@pytest.fixture
def blank_form() -> np.ndarray:
    return make_blank_form()


@pytest.fixture
def name_label_line() -> TextLine:
    return TextLine(text="Name:", confidence=0.99, box=NAME_LABEL_BOX)


@pytest.fixture
def name_slot() -> DetectedSlot:
    return DetectedSlot(label="Name", box=NAME_ANSWER_BOX)


@pytest.fixture
def template_store(tmp_path: Path) -> TemplateStore:
    return TemplateStore(tmp_path)


@pytest.fixture
def fake_field_reader() -> FakeFieldReader:
    return FakeFieldReader()


@pytest.fixture
def api_client(
    template_store: TemplateStore, name_slot: DetectedSlot, fake_field_reader: FakeFieldReader
) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_template_store] = lambda: template_store
    app.dependency_overrides[get_blank_form_field_detector] = lambda: FakeFieldDetector([name_slot])
    app.dependency_overrides[get_field_value_reader] = lambda: fake_field_reader
    app.dependency_overrides[get_ollama_client] = lambda: _unreachable_ollama_client()
    with TestClient(app) as client:
        yield client


def _unreachable_ollama_client() -> httpx.Client:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    return httpx.Client(base_url="http://ollama.test", transport=httpx.MockTransport(refuse))
