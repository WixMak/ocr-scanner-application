from dataclasses import dataclass
from typing import Protocol

import numpy as np

from app.schemas import BoundingBox, FieldStatus, FieldType


@dataclass(frozen=True)
class TextLine:
    text: str
    confidence: float
    box: BoundingBox


@dataclass(frozen=True)
class Reading:
    engine: str
    text: str
    confidence: float


@dataclass(frozen=True)
class FieldReading:
    value: str
    confidence: float
    status: FieldStatus
    readings: list[Reading]


class PageTextDetector(Protocol):
    def detect_lines(self, image: np.ndarray) -> list[TextLine]: ...


class CropReader(Protocol):
    name: str

    def read(self, crop: np.ndarray) -> Reading: ...


class FieldValueReader(Protocol):
    def read_field(self, crop: np.ndarray, field_type: FieldType) -> FieldReading: ...
