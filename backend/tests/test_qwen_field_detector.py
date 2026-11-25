import json
from collections.abc import Callable

import httpx
import numpy as np
import pytest

from app.errors import OcrEngineUnavailableError
from app.ocr.qwen_engine import EMPTY_THINKING_PREFILL
from app.ocr.qwen_field_detector import (
    DETECTION_CONTEXT_TOKENS,
    MAX_DETECTION_OUTPUT_TOKENS,
    QwenFieldDetector,
    QwenFieldSuggestions,
)
from app.schemas import FIELD_LABEL_MAX_LENGTH, BoundingBox, FieldType
from app.services.field_detection import DetectedOption, DetectedSlot

PAGE_WIDTH = 2000
PAGE_HEIGHT = 1000
PAGE = np.full((PAGE_HEIGHT, PAGE_WIDTH, 3), 255, dtype=np.uint8)


def make_detector(
    transport: httpx.MockTransport, *, should_skip_thinking: bool = True
) -> QwenFieldDetector:
    return QwenFieldDetector(
        model="qwen3-vl:4b",
        client=httpx.Client(base_url="http://ollama.test", transport=transport),
        keep_alive="5m",
        should_skip_thinking=should_skip_thinking,
    )


def respond_with_fields(fields: list[dict[str, object]]) -> httpx.MockTransport:
    content = json.dumps({"fields": [{"options": [], **field} for field in fields]})
    return httpx.MockTransport(
        lambda _request: httpx.Response(200, json={"message": {"content": content}})
    )


def test_scales_qwen_boxes_to_page_pixels_in_reading_order() -> None:
    transport = respond_with_fields(
        [
            {"label": "Date 日期", "type": "date", "bbox_2d": [500, 600, 900, 700]},
            {"label": " Name 姓名 ", "type": "text", "bbox_2d": [100, 100, 600, 150]},
        ]
    )

    slots = make_detector(transport).detect_fields(PAGE)

    assert slots == [
        DetectedSlot(
            label="Name 姓名",
            box=BoundingBox(x=200, y=100, width=1000, height=50),
            field_type=FieldType.TEXT,
        ),
        DetectedSlot(
            label="Date 日期",
            box=BoundingBox(x=1000, y=600, width=800, height=100),
            field_type=FieldType.DATE,
        ),
    ]


def test_choice_becomes_a_slot_with_one_option_per_tick_box() -> None:
    transport = respond_with_fields(
        [
            {
                "label": "Bank Account Type 銀行帳戶類別",
                "type": "choice",
                "bbox_2d": [0, 0, 1000, 1000],
                "options": [
                    {"label": "Personal 個人", "bbox_2d": [100, 300, 110, 320]},
                    {"label": " ", "bbox_2d": [200, 300, 210, 320]},
                    {"label": "Joint 聯名", "bbox_2d": [300, 300, 310, 320]},
                ],
            }
        ]
    )

    [slot] = make_detector(transport).detect_fields(PAGE)

    assert slot.field_type is FieldType.CHOICE
    assert slot.options == (
        DetectedOption(label="Personal 個人", box=BoundingBox(x=200, y=300, width=20, height=20)),
        DetectedOption(label="Joint 聯名", box=BoundingBox(x=600, y=300, width=20, height=20)),
    )
    assert slot.box == BoundingBox(x=200, y=300, width=420, height=20)


def test_choice_without_usable_options_is_skipped() -> None:
    transport = respond_with_fields(
        [
            {
                "label": "Account Type",
                "type": "choice",
                "bbox_2d": [100, 100, 600, 150],
                "options": [{"label": "Personal", "bbox_2d": [100, 300, 100, 320]}],
            }
        ]
    )

    assert make_detector(transport).detect_fields(PAGE) == []


def test_options_on_a_non_choice_field_are_ignored() -> None:
    transport = respond_with_fields(
        [
            {
                "label": "Name",
                "type": "text",
                "bbox_2d": [100, 100, 600, 150],
                "options": [{"label": "Mr", "bbox_2d": [100, 300, 110, 320]}],
            }
        ]
    )

    [slot] = make_detector(transport).detect_fields(PAGE)

    assert slot.field_type is FieldType.TEXT
    assert slot.options == ()


def test_clamps_boxes_that_run_off_the_page() -> None:
    transport = respond_with_fields(
        [{"label": "Remarks", "type": "text", "bbox_2d": [-20, 900, 1200, 1100]}]
    )

    [slot] = make_detector(transport).detect_fields(PAGE)

    assert slot.box == BoundingBox(x=0, y=900, width=PAGE_WIDTH, height=100)


def test_skips_empty_boxes_and_blank_labels() -> None:
    transport = respond_with_fields(
        [
            {"label": "Flat", "type": "text", "bbox_2d": [100, 100, 600, 100]},
            {"label": "Backwards", "type": "text", "bbox_2d": [600, 100, 100, 150]},
            {"label": "   ", "type": "text", "bbox_2d": [100, 100, 600, 150]},
        ]
    )

    assert make_detector(transport).detect_fields(PAGE) == []


def test_long_labels_are_cut_to_the_template_limit() -> None:
    transport = respond_with_fields(
        [{"label": "Note " * 100, "type": "text", "bbox_2d": [100, 100, 600, 150]}]
    )

    [slot] = make_detector(transport).detect_fields(PAGE)

    assert len(slot.label) == FIELD_LABEL_MAX_LENGTH


@pytest.mark.parametrize(
    "content",
    [
        "Sorry, I cannot help with that.",
        '{"fields": [{"label": "Name"',
        '{"fields": [{"label": "Name", "type": "signature", '
        '"bbox_2d": [1, 2, 3, 4], "options": []}]}',
        '{"fields": [{"label": "Name", "type": "text", "bbox_2d": [1, 2, 3, 4]}]}',
    ],
)
def test_unreadable_answer_gives_no_fields(content: str) -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, json={"message": {"content": content}})
    )

    assert make_detector(transport).detect_fields(PAGE) == []


def test_request_asks_for_structured_fields_with_room_for_a_full_page() -> None:
    requests: list[dict[str, object]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": '{"fields": []}'}})

    make_detector(httpx.MockTransport(respond)).detect_fields(PAGE)

    sent = requests[0]
    assert sent["model"] == "qwen3-vl:4b"
    assert sent["format"] == QwenFieldSuggestions.model_json_schema()
    assert sent["options"] == {
        "temperature": 0,
        "num_predict": MAX_DETECTION_OUTPUT_TOKENS,
        "num_ctx": DETECTION_CONTEXT_TOKENS,
    }
    assert len(sent["messages"][0]["images"]) == 1
    assert sent["messages"][-1] == {"role": "assistant", "content": EMPTY_THINKING_PREFILL}


def test_request_omits_prefill_for_instruct_models() -> None:
    requests: list[dict[str, object]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": '{"fields": []}'}})

    make_detector(httpx.MockTransport(respond), should_skip_thinking=False).detect_fields(PAGE)

    assert [message["role"] for message in requests[0]["messages"]] == ["user"]


def respond_with_server_error(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(500, json={"error": "model not found"})


def refuse_connection(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("refused", request=request)


@pytest.mark.parametrize("respond", [respond_with_server_error, refuse_connection])
def test_reports_engine_unavailable(respond: Callable[[httpx.Request], httpx.Response]) -> None:
    detector = make_detector(httpx.MockTransport(respond))

    with pytest.raises(OcrEngineUnavailableError):
        detector.detect_fields(PAGE)
