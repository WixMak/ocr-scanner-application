import os
import threading
from typing import Any

import cv2
import numpy as np

from app.imaging.page import WHITE_BGR
from app.ocr.text_normalisation import strip_fill_characters
from app.ocr.types import Reading, TextLine
from app.schemas import BoundingBox

PADDLE_ENGINE_NAME = "paddleocr"
PADDLE_LANGUAGE = "ch"  # PP-OCR's Chinese model also covers English letters and digits.
CROP_PADDING_PX = 16
SAME_ROW_TOLERANCE_PX = 12


class PaddleOcrEngine:
    name = PADDLE_ENGINE_NAME

    def __init__(self) -> None:
        # Skip PaddleX's online model-host check so the app starts offline once models are cached.
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
        from paddleocr import PaddleOCR

        self._ocr = PaddleOCR(
            lang=PADDLE_LANGUAGE,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
        # FastAPI runs sync endpoints on a thread pool; the Paddle predictor is not thread-safe.
        self._predict_lock = threading.Lock()

    def detect_lines(self, image: np.ndarray) -> list[TextLine]:
        with self._predict_lock:
            result = self._ocr.predict(image)[0]
        return parse_paddle_result(result)

    def read(self, crop: np.ndarray) -> Reading:
        padded = cv2.copyMakeBorder(
            crop,
            CROP_PADDING_PX,
            CROP_PADDING_PX,
            CROP_PADDING_PX,
            CROP_PADDING_PX,
            cv2.BORDER_CONSTANT,
            value=WHITE_BGR,
        )
        lines = self.detect_lines(padded)
        return combine_lines_into_reading(lines, engine=self.name)


def parse_paddle_result(result: Any) -> list[TextLine]:
    lines: list[TextLine] = []
    for text, score, box in zip(
        result["rec_texts"], result["rec_scores"], result["rec_boxes"], strict=True
    ):
        left, top, right, bottom = (int(value) for value in box)
        if right <= left or bottom <= top:
            continue
        lines.append(
            TextLine(
                text=str(text),
                confidence=float(score),
                box=BoundingBox(
                    x=max(left, 0), y=max(top, 0), width=right - left, height=bottom - top
                ),
            )
        )
    return lines


def combine_lines_into_reading(lines: list[TextLine], *, engine: str) -> Reading:
    meaningful_lines = [line for line in lines if strip_fill_characters(line.text)]
    if not meaningful_lines:
        return Reading(engine=engine, text="", confidence=0.0)
    ordered = sorted(meaningful_lines, key=_reading_order_key)
    text = " ".join(strip_fill_characters(line.text) for line in ordered)
    confidence = min(line.confidence for line in ordered)
    return Reading(engine=engine, text=text, confidence=confidence)


def _reading_order_key(line: TextLine) -> tuple[int, int]:
    return (line.box.y // SAME_ROW_TOLERANCE_PX, line.box.x)
