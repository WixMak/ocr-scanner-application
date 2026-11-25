import base64
import logging

import httpx
import numpy as np
from pydantic import BaseModel, ValidationError

from app.errors import OcrEngineUnavailableError
from app.imaging.page import enclosing_box, encode_png
from app.ocr.qwen_engine import EMPTY_THINKING_PREFILL, OllamaChatResponse
from app.schemas import FIELD_LABEL_MAX_LENGTH, BoundingBox, FieldType
from app.services.field_detection import DetectedOption, DetectedSlot

logger = logging.getLogger(__name__)

FIELD_DETECTION_PROMPT = (
    "This is one page of a blank form. List every place where a person is expected to fill "
    "something in: underlines, empty boxes, empty table cells, and tick boxes. "
    "For each one give: label - the printed label or question exactly as written, keeping both "
    "Chinese and English text, without a trailing colon; type - one of text, number, date, "
    "choice; bbox_2d - [x1, y1, x2, y2] of the empty answer area only (not the printed label). "
    "Tick boxes that answer the same question are ONE field of type choice: its label is the "
    "question, and options lists each tick box with its printed option text as label and the "
    "small square as bbox_2d. Every tick box on the page must be an option of some choice "
    "field. Other types have an empty options list. Example of a choice field: "
    '{"label": "Gender 性別", "type": "choice", "bbox_2d": [100, 300, 500, 320], "options": '
    '[{"label": "Male 男", "bbox_2d": [250, 302, 262, 316]}, '
    '{"label": "Female 女", "bbox_2d": [350, 302, 362, 316]}]}. '
    "Skip titles, instructions, and areas meant for office use."
)
# Qwen3-VL grounds boxes on a 0-1000 grid relative to the image, whatever its pixel size.
QWEN_COORDINATE_SCALE = 1000
# A dense page lists ~40 fields at ~40 tokens each; leave headroom so the JSON is never cut off.
MAX_DETECTION_OUTPUT_TOKENS = 4096
# A full A4 page at 200 DPI is ~4k image tokens; Ollama's default context would truncate it.
DETECTION_CONTEXT_TOKENS = 16384


class QwenChoiceOption(BaseModel):
    label: str
    bbox_2d: tuple[float, float, float, float]


class QwenFieldSuggestion(BaseModel):
    label: str
    type: FieldType
    bbox_2d: tuple[float, float, float, float]
    options: list[QwenChoiceOption]


class QwenFieldSuggestions(BaseModel):
    fields: list[QwenFieldSuggestion]


class QwenFieldDetector:
    """Asks Qwen3-VL to find the fill-in areas on a blank form page."""

    def __init__(
        self,
        *,
        model: str,
        client: httpx.Client,
        keep_alive: str,
        should_skip_thinking: bool,
    ) -> None:
        self._model = model
        self._client = client
        self._keep_alive = keep_alive
        self._should_skip_thinking = should_skip_thinking

    def detect_fields(self, image: np.ndarray) -> list[DetectedSlot]:
        try:
            response = self._client.post("/api/chat", json=self._build_request(image))
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise OcrEngineUnavailableError(self._model) from error
        chat_response = OllamaChatResponse.model_validate(response.json())
        suggestions = parse_field_suggestions(chat_response.message.content)
        page_height, page_width = image.shape[:2]
        slots = [
            to_detected_slot(suggestion, page_width=page_width, page_height=page_height)
            for suggestion in suggestions
        ]
        return sorted(
            (slot for slot in slots if slot is not None),
            key=lambda slot: (slot.box.y, slot.box.x),
        )

    def _build_request(self, image: np.ndarray) -> dict[str, object]:
        encoded_image = base64.b64encode(encode_png(image)).decode("ascii")
        messages: list[dict[str, object]] = [
            {"role": "user", "content": FIELD_DETECTION_PROMPT, "images": [encoded_image]}
        ]
        if self._should_skip_thinking:
            messages.append({"role": "assistant", "content": EMPTY_THINKING_PREFILL})
        return {
            "model": self._model,
            "stream": False,
            "think": False,
            "format": QwenFieldSuggestions.model_json_schema(),
            "keep_alive": self._keep_alive,
            "options": {
                "temperature": 0,
                "num_predict": MAX_DETECTION_OUTPUT_TOKENS,
                "num_ctx": DETECTION_CONTEXT_TOKENS,
            },
            "messages": messages,
        }


def parse_field_suggestions(content: str) -> list[QwenFieldSuggestion]:
    """An unreadable answer means no suggestions for the page; the user can still draw fields."""
    try:
        return QwenFieldSuggestions.model_validate_json(content).fields
    except ValidationError:
        logger.warning("Qwen returned an unreadable field list (%d characters)", len(content))
        return []


def to_detected_slot(
    suggestion: QwenFieldSuggestion, *, page_width: int, page_height: int
) -> DetectedSlot | None:
    label = _clean_label(suggestion.label)
    if not label:
        return None
    if suggestion.type is FieldType.CHOICE:
        return _to_choice_slot(
            label, suggestion.options, page_width=page_width, page_height=page_height
        )
    box = _scale_to_page(suggestion.bbox_2d, page_width=page_width, page_height=page_height)
    if box is None:
        return None
    return DetectedSlot(label=label, box=box, field_type=suggestion.type)


def _to_choice_slot(
    label: str, suggested_options: list[QwenChoiceOption], *, page_width: int, page_height: int
) -> DetectedSlot | None:
    """A choice's own box is derived from its options, so Qwen's box for the question is unused."""
    options = [
        _to_detected_option(option, page_width=page_width, page_height=page_height)
        for option in suggested_options
    ]
    usable_options = tuple(option for option in options if option is not None)
    if not usable_options:
        return None
    return DetectedSlot(
        label=label,
        box=enclosing_box([option.box for option in usable_options]),
        field_type=FieldType.CHOICE,
        options=usable_options,
    )


def _to_detected_option(
    option: QwenChoiceOption, *, page_width: int, page_height: int
) -> DetectedOption | None:
    label = _clean_label(option.label)
    box = _scale_to_page(option.bbox_2d, page_width=page_width, page_height=page_height)
    if not label or box is None:
        return None
    return DetectedOption(label=label, box=box)


def _clean_label(label: str) -> str:
    return label.strip()[:FIELD_LABEL_MAX_LENGTH]


def _scale_to_page(
    bbox: tuple[float, float, float, float], *, page_width: int, page_height: int
) -> BoundingBox | None:
    left, top, right, bottom = bbox
    pixel_left = _to_pixels(left, page_width)
    pixel_top = _to_pixels(top, page_height)
    pixel_right = _to_pixels(right, page_width)
    pixel_bottom = _to_pixels(bottom, page_height)
    if pixel_right <= pixel_left or pixel_bottom <= pixel_top:
        return None
    return BoundingBox(
        x=pixel_left,
        y=pixel_top,
        width=pixel_right - pixel_left,
        height=pixel_bottom - pixel_top,
    )


def _to_pixels(coordinate: float, page_length: int) -> int:
    clamped = min(max(coordinate, 0), QWEN_COORDINATE_SCALE)
    return round(clamped / QWEN_COORDINATE_SCALE * page_length)
