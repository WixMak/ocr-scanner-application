"""Runs the real PaddleOCR models and the local Ollama Qwen3-VL models.

Run with:  uv run pytest -m integration
"""

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from app.api.dependencies import get_field_value_reader, get_paddle_engine
from app.imaging.page import NORMALISED_PAGE_WIDTH
from app.schemas import FieldStatus, FieldType
from scripts.make_sample_forms import PRINTED_FONT_NAMES, find_font

pytestmark = pytest.mark.integration


def render_text(text: str, *, width: int, height: int) -> np.ndarray:
    page = Image.new("RGB", (width, height), "white")
    font = ImageFont.truetype(str(find_font(PRINTED_FONT_NAMES)), 36)
    ImageDraw.Draw(page).text((20, 20), text, font=font, fill="black")
    return cv2.cvtColor(np.array(page), cv2.COLOR_RGB2BGR)


def test_paddle_detects_bilingual_label_lines() -> None:
    page = render_text("姓名 Name:", width=NORMALISED_PAGE_WIDTH, height=200)

    lines = get_paddle_engine().detect_lines(page)

    assert any("Name" in line.text for line in lines)


def test_hybrid_reader_reads_mixed_chinese_and_digits() -> None:
    crop = render_text("电话 91234567", width=600, height=90)

    reading = get_field_value_reader().read_field(crop, FieldType.TEXT)

    assert reading.status is FieldStatus.CONFIRMED
    assert "91234567" in reading.value.replace(" ", "")
