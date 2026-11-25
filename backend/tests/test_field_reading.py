from dataclasses import dataclass

import numpy as np
import pytest

from app.ocr.field_readers import LanguageRoutedFieldReader, SingleEngineFieldReader
from app.ocr.text_normalisation import (
    has_chinese_characters,
    normalise_for_comparison,
    readings_match,
    strip_fill_characters,
)
from app.ocr.types import FieldReading
from app.schemas import FieldStatus, FieldType
from tests.conftest import FakeCropReader

FULLWIDTH_YEAR_2026 = (
    "\N{FULLWIDTH DIGIT TWO}\N{FULLWIDTH DIGIT ZERO}\N{FULLWIDTH DIGIT TWO}\N{FULLWIDTH DIGIT SIX}"
)
CHINESE_PUNCTUATION_ONLY = "\N{FULLWIDTH COMMA}\N{IDEOGRAPHIC FULL STOP}"
CROP = np.full((40, 120, 3), 255, dtype=np.uint8)
THRESHOLD = 0.85


@dataclass(frozen=True)
class Engines:
    layout: FakeCropReader
    fast: FakeCropReader
    accurate: FakeCropReader

    def make_reader(self) -> LanguageRoutedFieldReader:
        return LanguageRoutedFieldReader(
            layout_engine=self.layout,
            fast_engine=self.fast,
            accurate_engine=self.accurate,
            confidence_threshold=THRESHOLD,
        )

    def calls(self) -> tuple[int, int, int]:
        return (self.layout.call_count, self.fast.call_count, self.accurate.call_count)


def make_engines(
    *,
    paddle: tuple[str, float],
    fast: tuple[str, float] = ("", 0.0),
    accurate: tuple[str, float] = ("", 0.0),
) -> Engines:
    return Engines(
        layout=FakeCropReader("paddleocr", *paddle),
        fast=FakeCropReader("qwen-fast", *fast),
        accurate=FakeCropReader("qwen-accurate", *accurate),
    )


def engine_names(reading: FieldReading) -> list[str]:
    return [engine_reading.engine for engine_reading in reading.readings]


@pytest.mark.parametrize(
    ("paddle_confidence", "expected_status"),
    [(0.93, FieldStatus.CONFIRMED), (0.6, FieldStatus.REVIEW)],
)
def test_english_text_is_read_by_paddle_alone(
    paddle_confidence: float, expected_status: FieldStatus
) -> None:
    engines = make_engines(paddle=("Chan Tai Man", paddle_confidence))

    reading = engines.make_reader().read_field(CROP, FieldType.TEXT)

    assert reading.value == "Chan Tai Man"
    assert reading.status is expected_status
    assert engine_names(reading) == ["paddleocr"]
    assert engines.calls() == (1, 0, 0)


@pytest.mark.parametrize("paddle_text", ["陈大文", "Flat 5, 世纪大道100号", ""])
def test_chinese_or_unread_text_is_read_by_the_fast_model(paddle_text: str) -> None:
    engines = make_engines(paddle=(paddle_text, 0.7), fast=("世纪大道100号", 0.97))

    reading = engines.make_reader().read_field(CROP, FieldType.TEXT)

    assert reading.value == "世纪大道100号"
    assert reading.confidence == pytest.approx(0.97)
    assert reading.status is FieldStatus.CONFIRMED
    assert engine_names(reading) == ["paddleocr", "qwen-fast"]
    assert engines.calls() == (1, 1, 0)


def test_unsure_fast_model_reading_is_flagged_for_review() -> None:
    engines = make_engines(paddle=("陈大", 0.5), fast=("陈大文", 0.6))

    reading = engines.make_reader().read_field(CROP, FieldType.TEXT)

    assert reading.status is FieldStatus.REVIEW


@pytest.mark.parametrize(
    ("field_type", "paddle_text", "accurate_text"),
    [
        (FieldType.NUMBER, "9123 4567", "91234567"),
        (FieldType.DATE, FULLWIDTH_YEAR_2026 + "-11-20", "2026/11/20"),
    ],
)
def test_numbers_and_dates_are_confirmed_when_paddle_reads_the_same_digits(
    field_type: FieldType, paddle_text: str, accurate_text: str
) -> None:
    engines = make_engines(paddle=(paddle_text, 0.6), accurate=(accurate_text, 0.95))

    reading = engines.make_reader().read_field(CROP, field_type)

    assert reading.value == accurate_text
    assert reading.status is FieldStatus.CONFIRMED
    assert engine_names(reading) == ["paddleocr", "qwen-accurate"]
    assert engines.calls() == (1, 0, 1)


@pytest.mark.parametrize(
    ("paddle_text", "accurate_confidence"),
    [("1428", 0.95), ("1425", 0.5)],
)
def test_number_is_flagged_when_paddle_disagrees_or_the_accurate_model_is_unsure(
    paddle_text: str, accurate_confidence: float
) -> None:
    engines = make_engines(paddle=(paddle_text, 0.9), accurate=("1425", accurate_confidence))

    reading = engines.make_reader().read_field(CROP, FieldType.NUMBER)

    assert reading.value == "1425"
    assert reading.confidence == pytest.approx(accurate_confidence)
    assert reading.status is FieldStatus.REVIEW


@pytest.mark.parametrize(
    ("text", "confidence", "expected_status"),
    [
        ("28500", 0.9, FieldStatus.CONFIRMED),
        ("28500", 0.5, FieldStatus.REVIEW),
        ("", 0.99, FieldStatus.REVIEW),
    ],
)
def test_single_engine_reader_flags_low_confidence(
    text: str, confidence: float, expected_status: FieldStatus
) -> None:
    reader = SingleEngineFieldReader(
        FakeCropReader("paddleocr", text, confidence), confidence_threshold=THRESHOLD
    )

    reading = reader.read_field(CROP, FieldType.NUMBER)

    assert reading.status is expected_status
    assert reading.value == text


@pytest.mark.parametrize(
    ("first", "second", "field_type", "should_match"),
    [
        ("9123 4567", "91234567", FieldType.NUMBER, True),
        (
            FULLWIDTH_YEAR_2026 + "-11-20",
            "2026/11/20",
            FieldType.DATE,
            True,
        ),
        ("Chan Tai Man", "chantaiman", FieldType.TEXT, True),
        ("100号", "700号", FieldType.TEXT, False),
        ("", "", FieldType.TEXT, False),
    ],
)
def test_readings_match_by_field_type(
    first: str, second: str, field_type: FieldType, should_match: bool
) -> None:
    assert readings_match(first, second, field_type) is should_match


@pytest.mark.parametrize(
    ("text", "has_chinese"),
    [
        ("Chan Tai Man", False),
        ("陈大文", True),
        ("Room 5 室", True),
        (CHINESE_PUNCTUATION_ONLY, False),
        ("", False),
    ],
)
def test_has_chinese_characters(text: str, has_chinese: bool) -> None:
    assert has_chinese_characters(text) is has_chinese


def test_number_normalisation_keeps_decimal_point_and_sign() -> None:
    assert normalise_for_comparison("HK$ -1,425.50", FieldType.NUMBER) == "-1425.50"


def test_strip_fill_characters_removes_answer_lines() -> None:
    assert strip_fill_characters("  Name:_______ ") == "Name:"
