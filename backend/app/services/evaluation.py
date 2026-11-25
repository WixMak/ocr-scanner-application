from dataclasses import dataclass, field

from app.ocr.text_normalisation import normalise_for_comparison
from app.schemas import BoundingBox, ExtractedField, FieldType, TemplateField

DIGIT_FIELD_TYPES = (FieldType.NUMBER, FieldType.DATE)
# Intersection over union: a detected box must cover most of the saved box and not much more,
# so a thin strip beside a big signature box doesn't count as finding it.
MIN_FIELD_MATCH_OVERLAP = 0.5


@dataclass(frozen=True)
class FieldMismatch:
    sample: str
    key: str
    expected: str
    actual: str


@dataclass
class EngineScore:
    engine: str
    field_count: int = 0
    exact_match_count: int = 0
    digit_field_count: int = 0
    digit_exact_count: int = 0
    edit_distance_total: int = 0
    expected_character_total: int = 0
    page_count: int = 0
    seconds_total: float = 0.0
    mismatches: list[FieldMismatch] = field(default_factory=list)

    @property
    def exact_match_rate(self) -> float:
        return _safe_ratio(self.exact_match_count, self.field_count)

    @property
    def digit_exact_rate(self) -> float:
        return _safe_ratio(self.digit_exact_count, self.digit_field_count)

    @property
    def character_error_rate(self) -> float:
        return _safe_ratio(self.edit_distance_total, self.expected_character_total)

    @property
    def seconds_per_page(self) -> float:
        return _safe_ratio(self.seconds_total, self.page_count)


def record_page(
    score: EngineScore,
    *,
    sample: str,
    fields: list[ExtractedField],
    expected_values: dict[str, str],
    seconds: float,
) -> None:
    score.page_count += 1
    score.seconds_total += seconds
    for extracted in fields:
        if extracted.key not in expected_values:
            continue
        _record_field(
            score, sample=sample, extracted=extracted, expected=expected_values[extracted.key]
        )


def _record_field(
    score: EngineScore, *, sample: str, extracted: ExtractedField, expected: str
) -> None:
    expected_normalised = normalise_for_comparison(expected, extracted.field_type)
    actual_normalised = normalise_for_comparison(extracted.value, extracted.field_type)
    is_exact = expected_normalised == actual_normalised
    score.field_count += 1
    score.edit_distance_total += levenshtein_distance(expected_normalised, actual_normalised)
    score.expected_character_total += len(expected_normalised)
    if is_exact:
        score.exact_match_count += 1
    else:
        score.mismatches.append(
            FieldMismatch(
                sample=sample, key=extracted.key, expected=expected, actual=extracted.value
            )
        )
    if extracted.field_type in DIGIT_FIELD_TYPES:
        score.digit_field_count += 1
        if is_exact:
            score.digit_exact_count += 1


def levenshtein_distance(first: str, second: str) -> int:
    previous_row = list(range(len(second) + 1))
    for first_index, first_character in enumerate(first, start=1):
        current_row = [first_index]
        for second_index, second_character in enumerate(second, start=1):
            substitution_cost = 0 if first_character == second_character else 1
            current_row.append(
                min(
                    previous_row[second_index] + 1,
                    current_row[second_index - 1] + 1,
                    previous_row[second_index - 1] + substitution_cost,
                )
            )
        previous_row = current_row
    return previous_row[-1]


@dataclass(frozen=True)
class FieldMatch:
    expected: TemplateField
    detected: TemplateField

    @property
    def is_same_kind(self) -> bool:
        return self.expected.field_type is self.detected.field_type and len(
            self.expected.options
        ) == len(self.detected.options)


@dataclass(frozen=True)
class DetectionScore:
    """How closely detection on a blank form reproduces the fields saved in its template."""

    template_name: str
    matches: list[FieldMatch]
    missed: list[TemplateField]
    made_up: list[TemplateField]

    @property
    def expected_count(self) -> int:
        return len(self.matches) + len(self.missed)

    @property
    def detected_count(self) -> int:
        return len(self.matches) + len(self.made_up)

    @property
    def different_kind(self) -> list[FieldMatch]:
        return [match for match in self.matches if not match.is_same_kind]

    @property
    def recall(self) -> float:
        return _safe_ratio(len(self.matches), self.expected_count)

    @property
    def precision(self) -> float:
        return _safe_ratio(len(self.matches), self.detected_count)


@dataclass(frozen=True)
class _CandidatePair:
    overlap: float
    expected_index: int
    detected_index: int


def score_detection(
    template_name: str, *, expected: list[TemplateField], detected: list[TemplateField]
) -> DetectionScore:
    """Pair each saved field with a detected one, taking the most-overlapping pairs first."""
    matched_expected: set[int] = set()
    matched_detected: set[int] = set()
    matches = []
    for pair in _find_candidate_pairs(expected, detected):
        if pair.expected_index in matched_expected or pair.detected_index in matched_detected:
            continue
        matched_expected.add(pair.expected_index)
        matched_detected.add(pair.detected_index)
        matches.append(
            FieldMatch(
                expected=expected[pair.expected_index], detected=detected[pair.detected_index]
            )
        )
    return DetectionScore(
        template_name=template_name,
        matches=matches,
        missed=[field for index, field in enumerate(expected) if index not in matched_expected],
        made_up=[field for index, field in enumerate(detected) if index not in matched_detected],
    )


def _find_candidate_pairs(
    expected: list[TemplateField], detected: list[TemplateField]
) -> list[_CandidatePair]:
    pairs = []
    for expected_index, expected_field in enumerate(expected):
        for detected_index, detected_field in enumerate(detected):
            overlap = _overlap_on_same_page(expected_field, detected_field)
            if overlap >= MIN_FIELD_MATCH_OVERLAP:
                pairs.append(_CandidatePair(overlap, expected_index, detected_index))
    return sorted(pairs, key=lambda pair: pair.overlap, reverse=True)


def _overlap_on_same_page(first: TemplateField, second: TemplateField) -> float:
    if first.page_index != second.page_index:
        return 0.0
    return intersection_over_union(first.box, second.box)


def intersection_over_union(first: BoundingBox, second: BoundingBox) -> float:
    overlap_width = min(first.right, second.right) - max(first.x, second.x)
    overlap_height = min(first.bottom, second.bottom) - max(first.y, second.y)
    if overlap_width <= 0 or overlap_height <= 0:
        return 0.0
    overlap_area = overlap_width * overlap_height
    union_area = first.width * first.height + second.width * second.height - overlap_area
    return overlap_area / union_area


def _safe_ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0
