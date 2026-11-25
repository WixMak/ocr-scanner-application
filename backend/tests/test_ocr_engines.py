import json
import math
from collections.abc import Callable

import httpx
import numpy as np
import pytest

from app.errors import OcrEngineUnavailableError
from app.ocr.paddle_engine import combine_lines_into_reading, parse_paddle_result
from app.ocr.qwen_engine import (
    EMPTY_THINKING_PREFILL,
    OllamaTokenLogprob,
    QwenVlEngine,
    estimate_confidence,
    list_available_models,
)
from app.ocr.types import TextLine
from app.schemas import BoundingBox

CROP = np.full((40, 120, 3), 255, dtype=np.uint8)


def make_qwen_engine(
    handler: httpx.MockTransport, *, should_skip_thinking: bool = True
) -> QwenVlEngine:
    return QwenVlEngine(
        name="qwen-fast",
        model="qwen3-vl:4b",
        client=httpx.Client(base_url="http://ollama.test", transport=handler),
        keep_alive="5m",
        should_skip_thinking=should_skip_thinking,
    )


def test_qwen_reading_uses_least_certain_token_as_confidence() -> None:
    requests: list[dict[str, object]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "message": {"content": " 陈大文 \n"},
                "logprobs": [
                    {"token": "陈", "logprob": 0.0},
                    {"token": "大", "logprob": math.log(0.6)},
                    {"token": "文", "logprob": math.log(0.9)},
                ],
            },
        )

    reading = make_qwen_engine(httpx.MockTransport(respond)).read(CROP)

    assert reading.engine == "qwen-fast"
    assert reading.text == "陈大文"
    assert reading.confidence == pytest.approx(0.6)
    sent = requests[0]
    assert sent["model"] == "qwen3-vl:4b"
    assert sent["options"] == {"temperature": 0, "num_predict": 128}
    assert sent["messages"][-1] == {"role": "assistant", "content": EMPTY_THINKING_PREFILL}


def test_qwen_request_omits_prefill_for_instruct_models() -> None:
    requests: list[dict[str, object]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": "123"}})

    make_qwen_engine(httpx.MockTransport(respond), should_skip_thinking=False).read(CROP)

    assert [message["role"] for message in requests[0]["messages"]] == ["user"]


def test_qwen_empty_transcription_has_zero_confidence() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, json={"message": {"content": ""}})
    )

    reading = make_qwen_engine(transport).read(CROP)

    assert reading.text == ""
    assert reading.confidence == 0.0


@pytest.mark.parametrize(
    ("reply", "expected_text"),
    [
        ("The field appears to be a blank or mostly blank space with no text.", ""),
        ("This image shows an empty box.", ""),
        ("No visible handwriting text.", ""),
        ("The box is mostly blank.", ""),
        ("Nothing is written here.", ""),
        ("Chan Tai Man", "Chan Tai Man"),
    ],
)
def test_qwen_description_of_the_image_is_not_a_value(reply: str, expected_text: str) -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            json={
                "message": {"content": reply},
                "logprobs": [{"token": "x", "logprob": -0.01}],
            },
        )
    )

    reading = make_qwen_engine(transport).read(CROP)

    assert reading.text == expected_text
    assert (reading.confidence > 0) is bool(expected_text)


def respond_with_server_error(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(500, json={"error": "model not found"})


def refuse_connection(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("refused", request=request)


@pytest.mark.parametrize("respond", [respond_with_server_error, refuse_connection])
def test_qwen_reports_engine_unavailable(
    respond: Callable[[httpx.Request], httpx.Response],
) -> None:
    engine = make_qwen_engine(httpx.MockTransport(respond))

    with pytest.raises(OcrEngineUnavailableError):
        engine.read(CROP)


def test_estimate_confidence_without_logprobs_is_zero() -> None:
    assert estimate_confidence(None, has_text=True) == 0.0
    assert estimate_confidence([OllamaTokenLogprob(token="a", logprob=0.0)], has_text=False) == 0.0


def test_lists_installed_ollama_models() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200, json={"models": [{"name": "qwen3-vl:4b"}, {"name": "qwen3-vl:8b"}]}
        )
    )
    client = httpx.Client(base_url="http://ollama.test", transport=transport)

    assert list_available_models(client) == {"qwen3-vl:4b", "qwen3-vl:8b"}


def test_listing_models_returns_none_when_ollama_is_down() -> None:
    client = httpx.Client(
        base_url="http://ollama.test", transport=httpx.MockTransport(refuse_connection)
    )

    assert list_available_models(client) is None


def test_parses_paddle_result_and_skips_degenerate_boxes() -> None:
    result = {
        "rec_texts": ["姓名 Name:", "ghost"],
        "rec_scores": [0.98, 0.5],
        "rec_boxes": np.array([[10, 20, 110, 60], [5, 5, 5, 30]]),
    }

    lines = parse_paddle_result(result)

    assert lines == [
        TextLine(
            text="姓名 Name:", confidence=0.98, box=BoundingBox(x=10, y=20, width=100, height=40)
        )
    ]


def test_combines_lines_in_reading_order_and_drops_fill_characters() -> None:
    lines = [
        TextLine(text="Road", confidence=0.9, box=BoundingBox(x=200, y=60, width=80, height=30)),
        TextLine(
            text="88 Nathan", confidence=0.95, box=BoundingBox(x=10, y=62, width=150, height=30)
        ),
        TextLine(text="Flat 3A", confidence=0.8, box=BoundingBox(x=10, y=10, width=100, height=30)),
        TextLine(text="______", confidence=0.99, box=BoundingBox(x=10, y=100, width=300, height=8)),
    ]

    reading = combine_lines_into_reading(lines, engine="paddleocr")

    assert reading.text == "Flat 3A 88 Nathan Road"
    assert reading.confidence == pytest.approx(0.8)


def test_combining_no_meaningful_lines_gives_empty_reading() -> None:
    reading = combine_lines_into_reading([], engine="paddleocr")

    assert (reading.text, reading.confidence) == ("", 0.0)
