import numpy as np

from app.ocr.text_normalisation import has_chinese_characters, readings_match
from app.ocr.types import CropReader, FieldReading, Reading
from app.schemas import FieldStatus, FieldType

DIGIT_FIELD_TYPES = frozenset({FieldType.NUMBER, FieldType.DATE})


class SingleEngineFieldReader:
    """Reads every field with one engine; used by the engine comparison script."""

    def __init__(self, engine: CropReader, *, confidence_threshold: float) -> None:
        self._engine = engine
        self._confidence_threshold = confidence_threshold

    def read_field(self, crop: np.ndarray, field_type: FieldType) -> FieldReading:
        reading = self._engine.read(crop)
        is_confident = bool(reading.text) and reading.confidence >= self._confidence_threshold
        return FieldReading(
            value=reading.text,
            confidence=reading.confidence,
            status=FieldStatus.CONFIRMED if is_confident else FieldStatus.REVIEW,
            readings=[reading],
        )


class LanguageRoutedFieldReader:
    """PaddleOCR reads every field first, and its reading decides which engine gives the value.

    - Numbers and dates: the accurate VLM. Confirmed only when PaddleOCR reads the same digits,
      so a plausible-looking wrong digit is flagged for review instead of returned silently.
    - Text with Chinese characters, or text PaddleOCR could not read: the fast VLM.
    - Other text (English): PaddleOCR alone, which is about ten times faster than a VLM.
    """

    def __init__(
        self,
        *,
        layout_engine: CropReader,
        fast_engine: CropReader,
        accurate_engine: CropReader,
        confidence_threshold: float,
    ) -> None:
        self._layout_engine = layout_engine
        self._fast_engine = fast_engine
        self._accurate_engine = accurate_engine
        self._confidence_threshold = confidence_threshold

    def read_field(self, crop: np.ndarray, field_type: FieldType) -> FieldReading:
        layout_reading = self._layout_engine.read(crop)
        if field_type in DIGIT_FIELD_TYPES:
            accurate_reading = self._accurate_engine.read(crop)
            return self._choose(
                accurate_reading,
                readings=[layout_reading, accurate_reading],
                is_corroborated=readings_match(
                    accurate_reading.text, layout_reading.text, field_type
                ),
            )
        if layout_reading.text and not has_chinese_characters(layout_reading.text):
            return self._choose(layout_reading, readings=[layout_reading], is_corroborated=True)
        fast_reading = self._fast_engine.read(crop)
        return self._choose(
            fast_reading, readings=[layout_reading, fast_reading], is_corroborated=True
        )

    def _choose(
        self, chosen: Reading, *, readings: list[Reading], is_corroborated: bool
    ) -> FieldReading:
        is_confident = bool(chosen.text) and chosen.confidence >= self._confidence_threshold
        return FieldReading(
            value=chosen.text,
            confidence=chosen.confidence,
            status=FieldStatus.CONFIRMED
            if is_confident and is_corroborated
            else FieldStatus.REVIEW,
            readings=readings,
        )
