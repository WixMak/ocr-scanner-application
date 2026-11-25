import re
from uuid import uuid4

from app.schemas import FIELD_KEY_MAX_LENGTH, ChoiceOption, FieldType, TemplateField
from app.services.field_detection import DetectedOption, DetectedSlot

FALLBACK_KEY_PREFIX = "field"
ASCII_WORD_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9]*")
LEADING_DIGITS_PATTERN = re.compile(r"^[0-9_]+")

DATE_KEYWORDS = ("date", "dob", "birth", "日期", "出生", "生日")
NUMBER_KEYWORDS = (
    "phone",
    "tel",
    "mobile",
    "fax",
    "amount",
    "salary",
    "contribution",
    "age",
    "qty",
    "quantity",
    "电话",
    "電話",
    "手机",
    "手機",
    "传真",
    "傳真",
    "金额",
    "金額",
    "薪",
    "供款",
    "年龄",
    "年齡",
    "数量",
    "數量",
)


def suggest_template_fields(slots_by_page: list[list[DetectedSlot]]) -> list[TemplateField]:
    """Keys must be unique across the whole form, not just within one page."""
    used_keys: set[str] = set()
    fields = []
    for page_index, slots in enumerate(slots_by_page):
        for slot in slots:
            key = suggest_field_key(slot.label, used_keys)
            used_keys.add(key)
            fields.append(
                TemplateField(
                    id=uuid4().hex,
                    key=key,
                    label=slot.label,
                    field_type=_suggest_field_type(slot),
                    page_index=page_index,
                    box=slot.box,
                    options=[_to_choice_option(option) for option in slot.options],
                )
            )
    return fields


def _to_choice_option(option: DetectedOption) -> ChoiceOption:
    return ChoiceOption(id=uuid4().hex, label=option.label, box=option.box)


def suggest_field_key(label: str, used_keys: set[str]) -> str:
    """Build a snake_case key from the label's English words, e.g. '姓名 Full Name' -> full_name."""
    words = [word.lower() for word in ASCII_WORD_PATTERN.findall(label)]
    base_key = LEADING_DIGITS_PATTERN.sub("", "_".join(words))[:FIELD_KEY_MAX_LENGTH]
    if not base_key:
        return _first_unused_numbered_key(FALLBACK_KEY_PREFIX, used_keys, start=1)
    if base_key not in used_keys:
        return base_key
    return _first_unused_numbered_key(base_key, used_keys, start=2)


def _first_unused_numbered_key(prefix: str, used_keys: set[str], *, start: int) -> str:
    number = start
    while _numbered_key(prefix, number) in used_keys:
        number += 1
    return _numbered_key(prefix, number)


def _numbered_key(prefix: str, number: int) -> str:
    suffix = f"_{number}"
    trimmed_prefix = prefix[: FIELD_KEY_MAX_LENGTH - len(suffix)].rstrip("_")
    return f"{trimmed_prefix}{suffix}"


def _suggest_field_type(slot: DetectedSlot) -> FieldType:
    if slot.options:
        return FieldType.CHOICE
    if slot.field_type is not None:
        return slot.field_type
    return guess_field_type(slot.label)


def guess_field_type(label: str) -> FieldType:
    lowered = label.lower()
    if any(keyword in lowered for keyword in DATE_KEYWORDS):
        return FieldType.DATE
    if any(keyword in lowered for keyword in NUMBER_KEYWORDS):
        return FieldType.NUMBER
    return FieldType.TEXT
