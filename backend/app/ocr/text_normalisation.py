import re
import unicodedata

from app.schemas import FieldType

FILL_CHARACTERS = "_.…-—\N{FULLWIDTH LOW LINE}\N{FULLWIDTH FULL STOP}"
NON_DIGIT_PATTERN = re.compile(r"\D")
NUMBER_NOISE_PATTERN = re.compile(r"[^\d.\-]")
WHITESPACE_PATTERN = re.compile(r"\s+")
# CJK Unified Ideographs, Extension A, and Compatibility Ideographs.
CHINESE_CHARACTER_PATTERN = re.compile("[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def strip_fill_characters(text: str) -> str:
    """Remove the underscores and dot leaders a blank form uses as answer lines."""
    return text.strip().strip(FILL_CHARACTERS).strip()


def normalise_for_comparison(text: str, field_type: FieldType) -> str:
    """Reduce a reading to what matters when checking two engines agree."""
    folded = unicodedata.normalize("NFKC", text)
    if field_type is FieldType.DATE:
        return NON_DIGIT_PATTERN.sub("", folded)
    if field_type is FieldType.NUMBER:
        return NUMBER_NOISE_PATTERN.sub("", folded)
    return WHITESPACE_PATTERN.sub("", folded).casefold()


def readings_match(first: str, second: str, field_type: FieldType) -> bool:
    first_normalised = normalise_for_comparison(first, field_type)
    if not first_normalised:
        return False
    return first_normalised == normalise_for_comparison(second, field_type)


def has_chinese_characters(text: str) -> bool:
    return CHINESE_CHARACTER_PATTERN.search(text) is not None
