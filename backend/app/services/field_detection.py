import unicodedata
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from itertools import pairwise
from typing import Protocol

import cv2
import numpy as np

from app.imaging.page import enclosing_box, to_grayscale
from app.ocr.text_normalisation import strip_fill_characters
from app.ocr.types import CropReader, TextLine
from app.schemas import FIELD_LABEL_MAX_LENGTH, BoundingBox, FieldType

LABEL_SUFFIXES = (":", "\N{FULLWIDTH COLON}")
ADAPTIVE_BLOCK_SIZE = 31
ADAPTIVE_OFFSET = 15
HORIZONTAL_KERNEL_PAGE_FRACTION = 40
VERTICAL_KERNEL_PAGE_FRACTION = 60
MIN_KERNEL_LENGTH_PX = 15
MAX_RULE_THICKNESS_PX = 10
MIN_UNDERLINE_WIDTH_PX = 80
MIN_SLOT_WIDTH_PX = 60
MIN_CELL_WIDTH_PX = 60
MIN_CELL_HEIGHT_PX = 24
MAX_CELL_PAGE_AREA_FRACTION = 0.5
MAX_LABEL_TO_UNDERLINE_GAP_PX = 200
SLOT_GAP_PX = 6
CELL_BORDER_INSET_PX = 4
PAGE_MARGIN_PX = 40
UNDERLINE_SLOT_HEIGHT_RATIO = 1.8
SPACE_SLOT_PADDING_RATIO = 0.4
SAME_ROW_OVERLAP_RATIO = 0.5
DUPLICATE_SLOT_OVERLAP_RATIO = 0.5
WIDE_CHARACTER_WIDTHS = ("W", "F")
SECTION_DIVIDER_PAGE_WIDTH_FRACTION = 0.85
MAX_DASH_LENGTH_PX = 15
MAX_DASH_THICKNESS_PX = 4
MAX_DASH_GAP_PX = 10
MIN_CHECKBOX_SIDE_PX = 20
MAX_CHECKBOX_SIDE_PX = 60
MAX_CHECKBOX_SIDE_DIFFERENCE_RATIO = 0.2
MAX_CHECKBOX_INK_FILL_RATIO = 0.5
MAX_CHECKBOX_LABEL_GAP_PX = 40
MAX_CHECKBOX_LABEL_HEIGHT_RATIO = 1.5
MAX_BLANK_AREA_INK_FRACTION = 0.05
MIN_ANSWER_SPACE_HEIGHT_PX = 60
MAX_BLANK_ROW_INK_FRACTION = 0.01
MAX_SQUARE_SNAP_DISTANCE_PX = 60
TEXT_JOIN_GAP_PX = 21
TEXT_JOIN_LINE_GAP_PX = 3
MIN_TEXT_HEIGHT_PX = 8
MAX_TEXT_HEIGHT_PX = 60
MIN_TICK_BOX_CLEARANCE_PX = 8
MIN_TICK_BOX_LABEL_GAP_PX = 4
MIN_TICK_BOX_LEFT_CLEARANCE_PX = 16
MIN_TICK_BOX_TO_TEXT_HEIGHT_RATIO = 1.25
MAX_LABEL_ABOVE_BOX_GAP_PX = 20
LABEL_CROP_MARGIN_PX = 4
MAX_QUESTION_ABOVE_OPTIONS_GAP_PX = 60
MAX_STACKED_LABEL_LINE_GAP_PX = 10
MAX_STACKED_LABEL_INDENT_PX = 10
LINE_END_ALIGNMENT_PX = 20
TABLE_CELL_ALIGNMENT_PX = 8
MIN_TABLE_ANSWER_ROWS = 2
DARK_GRAY_LEVEL = 128
MIN_WRITING_HEIGHT_PX = 24
WRITING_SLOT_HEIGHT_PX = 42
MIN_CHARACTER_BOX_WIDTH_PX = 20
MAX_CHARACTER_BOX_HEIGHT_PX = 80
MIN_CHARACTER_BOXES_PER_ANSWER = 2
MIN_COMB_TICK_HEIGHT_PX = 20
MIN_SPACE_BELOW_TO_ABOVE_LABEL_RATIO = 2


@dataclass(frozen=True)
class DetectedOption:
    label: str
    box: BoundingBox
    label_box: BoundingBox | None = None


@dataclass(frozen=True)
class DetectedSlot:
    label: str
    box: BoundingBox
    field_type: FieldType | None = None
    options: tuple[DetectedOption, ...] = ()
    label_box: BoundingBox | None = None


class BlankFormFieldDetector(Protocol):
    def detect_fields(self, image: np.ndarray) -> list[DetectedSlot]: ...


@dataclass(frozen=True)
class OpenCvFieldDetector:
    """Finds fields from the page's ruling alone, then reads only the label beside each one."""

    label_reader: CropReader

    def detect_fields(self, image: np.ndarray) -> list[DetectedSlot]:
        slots = detect_field_slots(image, find_printed_text_lines(image))
        labels = _PageLabels(image=image, reader=self.label_reader)
        return [_read_slot_labels(slot, labels) for slot in slots]


@dataclass
class _PageLabels:
    """Every field in a table column shares its heading, so each label is read only once."""

    image: np.ndarray
    reader: CropReader
    read_labels: dict[tuple[int, int, int, int], str] = field(default_factory=dict)

    def read(self, label_box: BoundingBox | None) -> str:
        if label_box is None:
            return ""
        key = (label_box.x, label_box.y, label_box.width, label_box.height)
        if key not in self.read_labels:
            self.read_labels[key] = _read_label(self.image, label_box, self.reader)
        return self.read_labels[key]


def _read_slot_labels(slot: DetectedSlot, labels: _PageLabels) -> DetectedSlot:
    options = tuple(replace(option, label=labels.read(option.label_box)) for option in slot.options)
    return replace(slot, label=labels.read(slot.label_box), options=options)


def _read_label(image: np.ndarray, label_box: BoundingBox, reader: CropReader) -> str:
    top = max(label_box.y - LABEL_CROP_MARGIN_PX, 0)
    left = max(label_box.x - LABEL_CROP_MARGIN_PX, 0)
    crop = image[
        top : label_box.bottom + LABEL_CROP_MARGIN_PX,
        left : label_box.right + LABEL_CROP_MARGIN_PX,
    ]
    return _to_label(reader.read(crop).text)


def _to_label(text: str) -> str:
    without_fill = strip_fill_characters(text)
    return without_fill.rstrip("".join(LABEL_SUFFIXES)).strip()[:FIELD_LABEL_MAX_LENGTH]


@dataclass(frozen=True)
class LabelCandidate:
    label: str
    has_colon: bool
    line: TextLine
    text_end_x: int


@dataclass(frozen=True)
class PageRules:
    underlines: list[BoundingBox]
    cells: list[BoundingBox]
    character_boxes: list[BoundingBox]
    square_outlines: list[BoundingBox]
    non_rule_ink: np.ndarray


def detect_field_slots(image: np.ndarray, text_lines: list[TextLine]) -> list[DetectedSlot]:
    """Pair each printed label on a blank form with the empty area where its answer goes."""
    page_height, page_width = image.shape[:2]
    gray = to_grayscale(image)
    rules = find_page_rules(gray)
    tick_boxes = find_tick_box_options(rules.square_outlines, text_lines)
    checkboxes = [tick_box.box for tick_box in tick_boxes]
    slots = _find_table_column_slots(rules.cells, text_lines)
    column_headings = [slot.label_box for slot in slots if slot.label_box is not None]
    taken_boxes = [*checkboxes, *(slot.box for slot in slots)]
    write_on_lines = [
        underline
        for underline in rules.underlines
        if not _is_cell_border(underline, rules.cells) and not _is_edge_of_dark_bar(underline, gray)
    ]
    used_label_boxes: list[BoundingBox] = []
    for line in sorted(text_lines, key=lambda text_line: (text_line.box.y, text_line.box.x)):
        is_column_heading = _find_containing_cell(line.box, column_headings) is not None
        is_banner_heading = _is_dark_area(line.box, gray)
        if is_column_heading or is_banner_heading:
            continue
        if _is_hint_on_write_on_line(line.box, write_on_lines):
            continue
        candidate = parse_label_candidate(line)
        if candidate is None:
            continue
        slot_box = _find_slot_box(
            candidate, rules, text_lines, checkboxes=checkboxes, page_width=page_width
        )
        if slot_box is None or _overlaps_existing(slot_box, taken_boxes):
            continue
        clipped_box = _clip_to_page(slot_box, width=page_width, height=page_height)
        label_box = _join_stacked_line_above(line, text_lines, used_label_boxes=used_label_boxes)
        slots.append(DetectedSlot(label=candidate.label, box=clipped_box, label_box=label_box))
        taken_boxes.append(clipped_box)
        used_label_boxes.append(line.box)
    character_slots = _find_character_box_slots(rules, text_lines, taken_boxes=taken_boxes)
    taken_boxes.extend(slot.box for slot in character_slots)
    line_slots = _find_unclaimed_line_slots(
        rules, write_on_lines, text_lines, gray=gray, taken_boxes=taken_boxes
    )
    slots.extend([*character_slots, *line_slots])
    slots.extend(_group_tick_boxes_into_choices(tick_boxes, rules.cells, text_lines))
    return sorted(slots, key=lambda slot: (slot.box.y, slot.box.x))


def _find_character_box_slots(
    rules: PageRules, text_lines: list[TextLine], *, taken_boxes: list[BoundingBox]
) -> list[DetectedSlot]:
    """A run of adjoining empty one-character boxes holds one answer, such as a percentage."""
    slots = []
    for row in _group_into_rows(rules.character_boxes, _box_itself):
        for run in _split_into_empty_runs(row, rules.non_rule_ink):
            answer_box = enclosing_box(run)
            if len(run) < MIN_CHARACTER_BOXES_PER_ANSWER or _overlaps_existing(
                answer_box, taken_boxes
            ):
                continue
            label_box = _find_label_beside_or_above(answer_box, text_lines)
            slots.append(DetectedSlot(label="", box=answer_box, label_box=label_box))
    return slots


def _box_itself(box: BoundingBox) -> BoundingBox:
    return box


def _split_into_empty_runs(
    row: list[BoundingBox], non_rule_ink: np.ndarray
) -> list[list[BoundingBox]]:
    """Printed boxes, like a "%" sign or a pre-filled total, end a run."""
    runs: list[list[BoundingBox]] = []
    previous: BoundingBox | None = None
    for box in row:
        if not _is_blank(_inset_cell(box), non_rule_ink):
            previous = None
            continue
        if previous is not None and _adjoins(previous, box):
            runs[-1].append(box)
        else:
            runs.append([box])
        previous = box
    return runs


def _adjoins(left_box: BoundingBox, right_box: BoundingBox) -> bool:
    is_next_to = right_box.x - left_box.right <= TABLE_CELL_ALIGNMENT_PX
    is_same_height = abs(right_box.height - left_box.height) <= TABLE_CELL_ALIGNMENT_PX
    return is_next_to and is_same_height


def _find_unclaimed_line_slots(
    rules: PageRules,
    write_on_lines: list[BoundingBox],
    text_lines: list[TextLine],
    *,
    gray: np.ndarray,
    taken_boxes: list[BoundingBox],
) -> list[DetectedSlot]:
    """An empty write-on line no label claimed is still an answer: a second number on the same
    row, or a line printed under its question."""
    slots: list[DetectedSlot] = []
    for line in sorted(write_on_lines, key=lambda underline: (underline.y, underline.x)):
        if _is_rule_over_heading(line, text_lines):
            continue
        top = _top_below_line_above(line, line.y - WRITING_SLOT_HEIGHT_PX, rules.underlines)
        space = BoundingBox(x=line.x, y=top, width=line.width, height=line.bottom - top)
        slot_box = _below_printed_text(space, text_lines, rules.underlines, label_line=None)
        if slot_box is None or not _is_open_paper(slot_box, rules.non_rule_ink, gray):
            continue
        if _overlaps_existing(slot_box, [*taken_boxes, *(slot.box for slot in slots)]):
            continue
        label_box = _find_label_beside_or_above(slot_box, text_lines)
        slots.append(DetectedSlot(label="", box=slot_box, label_box=label_box))
    return slots


def _is_open_paper(box: BoundingBox, non_rule_ink: np.ndarray, gray: np.ndarray) -> bool:
    """Blank paper apart from comb ticks: underlined words and banner edges have ink or black
    above them."""
    if _is_dark_area(box, gray):
        return False
    area = non_rule_ink[box.y : box.bottom, box.x : box.right]
    tick_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, MIN_COMB_TICK_HEIGHT_PX))
    comb_ticks = cv2.morphologyEx(area, cv2.MORPH_OPEN, tick_kernel)
    ink_without_ticks = cv2.subtract(area, comb_ticks)
    return np.count_nonzero(ink_without_ticks) <= area.size * MAX_BLANK_AREA_INK_FRACTION


def _is_rule_over_heading(line: BoundingBox, text_lines: list[TextLine]) -> bool:
    """Text printed right under a line and nearly as wide is a heading ruled off above it."""
    return any(
        abs(text.box.x - line.x) <= LINE_END_ALIGNMENT_PX
        and 0 <= text.box.y - line.bottom <= text.box.height
        and line.right - text.box.right < MIN_SLOT_WIDTH_PX
        for text in text_lines
    )


def _find_label_beside_or_above(
    answer_box: BoundingBox, text_lines: list[TextLine]
) -> BoundingBox | None:
    """The text just before the answer on its row names it, or else the text just above it."""
    before = [
        line.box
        for line in text_lines
        if _share_row(line.box, answer_box) and line.box.right <= answer_box.x
    ]
    if before:
        return max(before, key=lambda box: box.right)
    above = [
        line.box
        for line in text_lines
        if 0 <= answer_box.y - line.box.bottom <= WRITING_SLOT_HEIGHT_PX
        and line.box.x < answer_box.right
        and answer_box.x < line.box.right
    ]
    return max(above, key=lambda box: box.bottom, default=None)


def _find_table_column_slots(
    cells: list[BoundingBox], text_lines: list[TextLine]
) -> list[DetectedSlot]:
    """A table's heading cell names the empty rows stacked under it: one field per row.
    One empty cell under a label is just a box form, which the label rules already handle."""
    slots = []
    for heading_cell in cells:
        heading_lines = [
            line.box for line in text_lines if _find_containing_cell(line.box, [heading_cell])
        ]
        answer_cells = _find_empty_cells_below(heading_cell, cells, text_lines)
        if not heading_lines or len(answer_cells) < MIN_TABLE_ANSWER_ROWS:
            continue
        heading_box = enclosing_box(heading_lines)
        slots.extend(
            DetectedSlot(label="", box=_inset_cell(answer_cell), label_box=heading_box)
            for answer_cell in answer_cells
        )
    return slots


def _find_empty_cells_below(
    heading_cell: BoundingBox, cells: list[BoundingBox], text_lines: list[TextLine]
) -> list[BoundingBox]:
    """Empty cells within the heading's columns, running down without a gap from the heading."""
    tolerance = TABLE_CELL_ALIGNMENT_PX
    empty_cells_below = sorted(
        (
            cell
            for cell in cells
            if cell.x >= heading_cell.x - tolerance
            and cell.right <= heading_cell.right + tolerance
            and cell.y >= heading_cell.bottom - tolerance
            and _shares_a_column_edge(cell, heading_cell)
            and not _contains_text(cell, text_lines)
        ),
        key=lambda cell: cell.y,
    )
    stacked_cells = []
    reached_bottom = heading_cell.bottom
    for cell in empty_cells_below:
        if cell.y - reached_bottom > tolerance:
            break
        stacked_cells.append(cell)
        reached_bottom = max(reached_bottom, cell.bottom)
    return stacked_cells


def _shares_a_column_edge(cell: BoundingBox, heading_cell: BoundingBox) -> bool:
    """A heading may also span a narrow row-label column, but not a whole page section."""
    tolerance = TABLE_CELL_ALIGNMENT_PX
    is_edge_aligned = (
        abs(cell.x - heading_cell.x) <= tolerance
        or abs(cell.right - heading_cell.right) <= tolerance
    )
    return is_edge_aligned and cell.width * 2 >= heading_cell.width


def _is_edge_of_a_box_not_written_on(underline: BoundingBox, rules: PageRules) -> bool:
    """A line edging a box that already holds print belongs to that printed panel."""
    return any(
        _is_edged_by(cell, underline) and not _is_blank(cell, rules.non_rule_ink)
        for cell in rules.cells
    )


def _is_edged_by(cell: BoundingBox, underline: BoundingBox) -> bool:
    """A border lies just outside the paper it closes; a comb's base inside a box does not."""
    overlaps_columns = cell.x < underline.right and underline.x < cell.right
    is_top_edge = _is_just_beyond(cell.y - underline.bottom)
    is_bottom_edge = _is_just_beyond(underline.y - cell.bottom)
    return overlaps_columns and (is_top_edge or is_bottom_edge)


def _is_just_beyond(distance_outward: int) -> bool:
    return -CELL_BORDER_INSET_PX <= distance_outward <= TABLE_CELL_ALIGNMENT_PX


def _is_edge_of_dark_bar(underline: BoundingBox, gray: np.ndarray) -> bool:
    """Heading bars are black; their top or bottom edge, broken up by white lettering, is no
    write-on line."""
    band = MAX_RULE_THICKNESS_PX
    below = BoundingBox(x=underline.x, y=underline.bottom, width=underline.width, height=band)
    above_top = max(underline.y - band, 0)
    above = BoundingBox(x=underline.x, y=above_top, width=underline.width, height=band)
    return _is_dark_area(below, gray) or _is_dark_area(above, gray)


def _is_cell_border(underline: BoundingBox, cells: list[BoundingBox]) -> bool:
    return any(_is_edged_by(cell, underline) for cell in cells)


def _is_hint_on_write_on_line(box: BoundingBox, underlines: list[BoundingBox]) -> bool:
    """Separators and format hints such as "/" or "DD / MM / YYYY" sit on or under the write-on
    line itself, which runs on past them at both ends; a label starts before its line."""
    return any(
        underline.x < box.x - LINE_END_ALIGNMENT_PX
        and underline.right > box.right + LINE_END_ALIGNMENT_PX
        and box.y - box.height // 2 <= underline.y <= box.bottom + SLOT_GAP_PX
        for underline in underlines
    )


def _join_stacked_line_above(
    line: TextLine, text_lines: list[TextLine], *, used_label_boxes: list[BoundingBox]
) -> BoundingBox:
    """Bilingual labels print English above Chinese; the field's line is beside the lower one."""
    stacked_above = [
        other.box
        for other in text_lines
        if other.box not in used_label_boxes
        and abs(other.box.x - line.box.x) <= MAX_STACKED_LABEL_INDENT_PX
        and 0 <= line.box.y - other.box.bottom <= MAX_STACKED_LABEL_LINE_GAP_PX
    ]
    if not stacked_above:
        return line.box
    return enclosing_box([*stacked_above[:1], line.box])


def refine_detected_slots(image: np.ndarray, slots: list[DetectedSlot]) -> list[DetectedSlot]:
    """Fit loosely placed boxes onto the form's own ruling: empty cell space and tick squares."""
    rules = find_page_rules(to_grayscale(image))
    return [_refine_slot(slot, rules) for slot in slots]


def _refine_slot(slot: DetectedSlot, rules: PageRules) -> DetectedSlot:
    if slot.options:
        options = _snap_options_to_squares(slot.options, rules.square_outlines)
        return replace(slot, options=options, box=enclosing_box([option.box for option in options]))
    answer_space = _find_answer_space_in_cell(slot.box, rules)
    if answer_space is None:
        return slot
    return replace(slot, box=answer_space)


def _find_answer_space_in_cell(box: BoundingBox, rules: PageRules) -> BoundingBox | None:
    """Signature and date cells print the label at the top and leave the space below it empty."""
    cell = _find_containing_cell(box, rules.cells)
    if cell is None:
        return None
    return _find_blank_space_in_cell(
        cell, rules, top=max(box.bottom, cell.y + CELL_BORDER_INSET_PX)
    )


def _find_answer_space_in_box_below(label_box: BoundingBox, rules: PageRules) -> BoundingBox | None:
    """Signature boxes often print their label just above the box, starting at its left edge."""
    box_below = next(
        (
            cell
            for cell in rules.cells
            if 0 <= cell.y - label_box.bottom <= MAX_LABEL_ABOVE_BOX_GAP_PX
            and cell.x - LINE_END_ALIGNMENT_PX <= label_box.x <= cell.right
        ),
        None,
    )
    if box_below is None:
        return None
    return _find_blank_space_in_cell(box_below, rules, top=box_below.y + CELL_BORDER_INSET_PX)


def _find_blank_space_in_cell(
    cell: BoundingBox, rules: PageRules, *, top: int
) -> BoundingBox | None:
    left = cell.x + CELL_BORDER_INSET_PX
    right = cell.right - CELL_BORDER_INSET_PX
    bottom = cell.bottom - CELL_BORDER_INSET_PX
    if bottom - top < MIN_ANSWER_SPACE_HEIGHT_PX:
        return None
    band_top, band_height = _find_tallest_blank_band(rules.non_rule_ink[top:bottom, left:right])
    if band_height < MIN_ANSWER_SPACE_HEIGHT_PX:
        return None
    return BoundingBox(x=left, y=top + band_top, width=right - left, height=band_height)


def _find_tallest_blank_band(area: np.ndarray) -> tuple[int, int]:
    """Return (top row, height) of the tallest run of rows with no printed ink."""
    max_ink_per_row = area.shape[1] * MAX_BLANK_ROW_INK_FRACTION
    is_blank_row = np.count_nonzero(area, axis=1) <= max_ink_per_row
    tallest_top, tallest_height = 0, 0
    run_top = 0
    for row, is_blank in enumerate(is_blank_row):
        if not is_blank:
            run_top = row + 1
            continue
        run_height = row + 1 - run_top
        if run_height > tallest_height:
            tallest_top, tallest_height = run_top, run_height
    return tallest_top, tallest_height


def _snap_options_to_squares(
    options: tuple[DetectedOption, ...], squares: list[BoundingBox]
) -> tuple[DetectedOption, ...]:
    unused_squares = list(squares)
    snapped = []
    for option in options:
        square = _find_nearest_square(option.box, unused_squares)
        if square is None:
            snapped.append(option)
            continue
        unused_squares.remove(square)
        snapped.append(replace(option, box=square))
    return tuple(snapped)


def _find_nearest_square(box: BoundingBox, squares: list[BoundingBox]) -> BoundingBox | None:
    nearby = [
        square for square in squares if _square_distance(square, box) <= MAX_SQUARE_SNAP_DISTANCE_PX
    ]
    return min(nearby, key=lambda square: _square_distance(square, box), default=None)


def _square_distance(square: BoundingBox, box: BoundingBox) -> float:
    """Distance from the square's centre to the nearest edge of the box (0 when inside it)."""
    centre_x = square.x + square.width / 2
    centre_y = square.y + square.height / 2
    horizontal_gap = max(box.x - centre_x, 0, centre_x - box.right)
    vertical_gap = max(box.y - centre_y, 0, centre_y - box.bottom)
    return float(np.hypot(horizontal_gap, vertical_gap))


def find_printed_text_lines(image: np.ndarray) -> list[TextLine]:
    """Join printed marks into line boxes; the text itself stays unread, so it is empty."""
    rules = find_page_rules(to_grayscale(image))
    text_ink = rules.non_rule_ink.copy()
    for square in rules.square_outlines:
        text_ink[square.y : square.bottom, square.x : square.right] = 0
    joined = cv2.morphologyEx(
        text_ink,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (TEXT_JOIN_GAP_PX, TEXT_JOIN_LINE_GAP_PX)),
    )
    region_count, _, stats, _ = cv2.connectedComponentsWithStats(joined)
    lines = []
    for region in range(1, region_count):
        x, y, width, height, _ = (int(value) for value in stats[region])
        if _is_text_line_sized(width=width, height=height):
            box = BoundingBox(x=x, y=y, width=width, height=height)
            lines.append(TextLine(text="", confidence=0.0, box=box))
    return lines


def _is_text_line_sized(*, width: int, height: int) -> bool:
    """Leftover comb ticks are thin strokes; logos and QR codes are taller than a text line."""
    is_wider_than_a_rule = width > MAX_RULE_THICKNESS_PX
    return is_wider_than_a_rule and MIN_TEXT_HEIGHT_PX <= height <= MAX_TEXT_HEIGHT_PX


def find_tick_box_options(
    square_outlines: list[BoundingBox], text_lines: list[TextLine]
) -> list[DetectedOption]:
    """A tick box is a small empty square with its option text printed just to the right."""
    options = []
    for square in square_outlines:
        if _find_containing_cell(square, [line.box for line in text_lines]) is not None:
            continue
        label_line = _find_checkbox_label_line(square, text_lines)
        if label_line is None:
            continue
        candidate = parse_label_candidate(label_line)
        if candidate is None:
            continue
        options.append(DetectedOption(label=candidate.label, box=square, label_box=label_line.box))
    return options


def _group_tick_boxes_into_choices(
    tick_boxes: list[DetectedOption], cells: list[BoundingBox], text_lines: list[TextLine]
) -> list[DetectedSlot]:
    """Tick boxes in the same table cell answer one question, so they form one choice field."""
    options_by_cell: dict[int, list[DetectedOption]] = defaultdict(list)
    lone_tick_boxes = []
    for tick_box in tick_boxes:
        cell = _find_containing_cell(tick_box.box, cells)
        if cell is None:
            lone_tick_boxes.append(tick_box)
            continue
        options_by_cell[cells.index(cell)].append(tick_box)
    choices = [
        _to_choice_slot(
            options, question_line=_find_question_line(cells[cell_index], options, text_lines)
        )
        for cell_index, options in options_by_cell.items()
    ]
    open_page_choices = [
        _to_open_page_choice_slot(options, text_lines)
        for options in _group_open_page_tick_boxes(lone_tick_boxes, text_lines)
    ]
    return [*choices, *open_page_choices]


def _to_open_page_choice_slot(
    options: list[DetectedOption], text_lines: list[TextLine]
) -> DetectedSlot:
    question_line = _find_open_page_question_line(options, text_lines)
    choice = _to_choice_slot(options, question_line=question_line)
    if question_line is None:
        return choice
    question_box = _join_stacked_line_above(question_line, text_lines, used_label_boxes=[])
    return replace(choice, label_box=question_box)


def _group_open_page_tick_boxes(
    tick_boxes: list[DetectedOption], text_lines: list[TextLine]
) -> list[list[DetectedOption]]:
    """Outside tables, one question's tick boxes share a row or are stacked in one column."""
    groups: list[list[DetectedOption]] = []
    for row in _group_into_rows(tick_boxes, _box_of_option):
        if groups and _continues_stacked_list(groups[-1], row, text_lines):
            groups[-1].extend(row)
            continue
        groups.append(row)
    return groups


def _group_into_rows[Item](
    items: list[Item], box_of: Callable[[Item], BoundingBox]
) -> list[list[Item]]:
    rows: list[list[Item]] = []
    for item in sorted(items, key=lambda item: box_of(item).y):
        if rows and _share_row(box_of(rows[-1][0]), box_of(item)):
            rows[-1].append(item)
            continue
        rows.append([item])
    return [sorted(row, key=lambda item: box_of(item).x) for row in rows]


def _box_of_option(option: DetectedOption) -> BoundingBox:
    return option.box


def _continues_stacked_list(
    group: list[DetectedOption], row: list[DetectedOption], text_lines: list[TextLine]
) -> bool:
    """A lower box in the same column answers the same question unless a new question starts."""
    first_box = group[0].box
    previous_box = group[-1].box
    row_box = row[0].box
    is_same_column = all(
        abs(row_box.x - column_box.x) <= column_box.width // 2
        for column_box in (first_box, previous_box)
    )
    starts_new_question = any(
        line.box.x < first_box.x and previous_box.bottom <= line.box.y < row_box.y
        for line in text_lines
    )
    return len(row) == 1 and is_same_column and not starts_new_question


def _find_open_page_question_line(
    options: list[DetectedOption], text_lines: list[TextLine]
) -> TextLine | None:
    """The question is printed to the left of the first tick box, or just above the boxes."""
    first_option = options[0].box
    option_label_boxes = [option.label_box for option in options]
    question_lines = [line for line in text_lines if line.box not in option_label_boxes]
    on_same_row = [
        line
        for line in question_lines
        if _share_row(line.box, first_option) and line.box.right <= first_option.x
    ]
    if on_same_row:
        return max(on_same_row, key=lambda line: line.box.right)
    above = [
        line
        for line in question_lines
        if line.box.x <= first_option.right
        and 0 <= first_option.y - line.box.bottom <= MAX_QUESTION_ABOVE_OPTIONS_GAP_PX
    ]
    if not above:
        return None
    nearest = max(above, key=lambda line: line.box.bottom)
    nearest_row = [line for line in above if _share_row(line.box, nearest.box)]
    return max(nearest_row, key=lambda line: line.box.width)


def _find_question_line(
    cell: BoundingBox, options: list[DetectedOption], text_lines: list[TextLine]
) -> TextLine | None:
    """The question is printed above the tick boxes or to the left of the first one."""
    first_option = _in_reading_order(options)[0].box
    option_label_boxes = [option.label_box for option in options]
    questions = [
        line
        for line in text_lines
        if line.box not in option_label_boxes
        and _find_containing_cell(line.box, [cell]) is not None
        and _is_before_option(line.box, first_option)
    ]
    return min(questions, key=lambda line: (line.box.y, line.box.x), default=None)


def _is_before_option(box: BoundingBox, option: BoundingBox) -> bool:
    is_above = box.bottom <= option.y
    is_left_on_same_row = _share_row(box, option) and box.right <= option.x
    return is_above or is_left_on_same_row


def _to_choice_slot(
    options: list[DetectedOption], *, question_line: TextLine | None
) -> DetectedSlot:
    ordered = _in_reading_order(options)
    choice = DetectedSlot(
        label="",
        box=enclosing_box([option.box for option in ordered]),
        field_type=FieldType.CHOICE,
        options=ordered,
    )
    if question_line is None:
        return choice
    return replace(choice, label=_to_label(question_line.text), label_box=question_line.box)


def _in_reading_order(options: list[DetectedOption]) -> tuple[DetectedOption, ...]:
    """Squares on one printed row can sit a pixel apart, so group rows before sorting across."""
    return tuple(option for row in _group_into_rows(options, _box_of_option) for option in row)


def parse_label_candidate(line: TextLine) -> LabelCandidate | None:
    if not line.text:
        # Found by shape alone: the user names the field, and no colon can be seen.
        return LabelCandidate(label="", has_colon=False, line=line, text_end_x=line.box.right)
    without_fill = strip_fill_characters(line.text)
    has_colon = without_fill.endswith(LABEL_SUFFIXES)
    label = _to_label(line.text)
    if not label:
        return None
    text_share = _display_width(without_fill) / max(_display_width(line.text.strip()), 1)
    text_end_x = line.box.x + round(line.box.width * min(text_share, 1.0))
    return LabelCandidate(label=label, has_colon=has_colon, line=line, text_end_x=text_end_x)


def find_page_rules(gray: np.ndarray) -> PageRules:
    page_height, page_width = gray.shape[:2]
    ink = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        ADAPTIVE_BLOCK_SIZE,
        ADAPTIVE_OFFSET,
    )
    horizontal_length = max(page_width // HORIZONTAL_KERNEL_PAGE_FRACTION, MIN_KERNEL_LENGTH_PX)
    vertical_length = max(page_height // VERTICAL_KERNEL_PAGE_FRACTION, MIN_KERNEL_LENGTH_PX)
    solid_horizontal = cv2.morphologyEx(
        ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (horizontal_length, 1))
    )
    dashed_horizontal = _find_dashed_horizontal_rules(ink, min_length=horizontal_length)
    horizontal = cv2.bitwise_or(solid_horizontal, dashed_horizontal)
    vertical = cv2.morphologyEx(
        ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, vertical_length))
    )
    # Dashed lines stop a few pixels short of the borders they meet; join them so boxes close.
    dashed_joined_to_borders = cv2.morphologyEx(
        cv2.bitwise_or(dashed_horizontal, vertical),
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (MAX_DASH_GAP_PX + 1, 1)),
    )
    rule_mask = cv2.bitwise_or(solid_horizontal, dashed_joined_to_borders)
    non_rule_ink = cv2.bitwise_and(ink, cv2.bitwise_not(rule_mask))
    enclosed_paper = [
        region for region in _find_enclosed_regions(rule_mask) if not _is_dark_area(region, gray)
    ]
    return PageRules(
        underlines=_find_horizontal_segments(horizontal),
        cells=[region for region in enclosed_paper if _is_cell_sized(region)],
        character_boxes=[region for region in enclosed_paper if _is_character_box_sized(region)],
        square_outlines=[
            square
            for square in _find_square_outlines(ink)
            if _stands_apart_from_printed_text(square, non_rule_ink)
        ],
        non_rule_ink=non_rule_ink,
    )


def _find_dashed_horizontal_rules(ink: np.ndarray, *, min_length: int) -> np.ndarray:
    """Join rows of short dashes or dots into solid lines so dashed borders close their boxes."""
    _, labels, stats, _ = cv2.connectedComponentsWithStats(ink)
    is_dash = (stats[:, cv2.CC_STAT_WIDTH] <= MAX_DASH_LENGTH_PX) & (
        stats[:, cv2.CC_STAT_HEIGHT] <= MAX_DASH_THICKNESS_PX
    )
    dashes = np.where(is_dash[labels], 255, 0).astype(np.uint8)
    bridged = cv2.morphologyEx(
        dashes, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (MAX_DASH_GAP_PX + 1, 1))
    )
    return cv2.morphologyEx(
        bridged, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (min_length, 1))
    )


def _find_horizontal_segments(horizontal_mask: np.ndarray) -> list[BoundingBox]:
    """Write-on lines; page-wide lines are section dividers or table borders, not answer lines."""
    max_underline_width = horizontal_mask.shape[1] * SECTION_DIVIDER_PAGE_WIDTH_FRACTION
    contours, _ = cv2.findContours(horizontal_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    segments = []
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        is_line_sized = MIN_UNDERLINE_WIDTH_PX <= width < max_underline_width
        if is_line_sized and height <= MAX_RULE_THICKNESS_PX:
            segments.append(BoundingBox(x=x, y=y, width=width, height=height))
    return segments


def _find_square_outlines(ink: np.ndarray) -> list[BoundingBox]:
    region_count, _, stats, _ = cv2.connectedComponentsWithStats(ink)
    squares = []
    for region in range(1, region_count):
        x, y, width, height, ink_area = (int(value) for value in stats[region])
        if _is_checkbox_outline(width=width, height=height, ink_area=ink_area):
            squares.append(BoundingBox(x=x, y=y, width=width, height=height))
    return squares


def _stands_apart_from_printed_text(square: BoundingBox, non_rule_ink: np.ndarray) -> bool:
    """Square characters such as 口 sit among characters as tall as they are. A tick box has clear
    space above, below and well to its left, and the option text close to its right is shorter.
    """
    margin = MIN_TICK_BOX_CLEARANCE_PX
    top = max(square.y - margin, 0)
    left = max(square.x - MIN_TICK_BOX_LEFT_CLEARANCE_PX, 0)
    surrounding_ink = np.count_nonzero(
        non_rule_ink[top : square.bottom + margin, left : square.right + MIN_TICK_BOX_LABEL_GAP_PX]
    )
    own_ink = np.count_nonzero(non_rule_ink[square.y : square.bottom, square.x : square.right])
    if surrounding_ink != own_ink:
        return False
    text_height = _measure_first_text_row_beside(square, non_rule_ink)
    return text_height * MIN_TICK_BOX_TO_TEXT_HEIGHT_RATIO <= square.height


def _measure_first_text_row_beside(square: BoundingBox, non_rule_ink: np.ndarray) -> int:
    """Height of the topmost run of inked rows just right of the square, or 0 when there is none."""
    margin = MIN_TICK_BOX_CLEARANCE_PX
    beside = non_rule_ink[
        max(square.y - margin, 0) : square.bottom + margin,
        square.right + MIN_TICK_BOX_LABEL_GAP_PX : square.right + MAX_CHECKBOX_LABEL_GAP_PX,
    ]
    inked_rows = np.flatnonzero(np.count_nonzero(beside, axis=1))
    if inked_rows.size == 0:
        return 0
    row_breaks = np.flatnonzero(np.diff(inked_rows) > 1)
    first_run_end = inked_rows[row_breaks[0]] if row_breaks.size else inked_rows[-1]
    return int(first_run_end - inked_rows[0] + 1)


def _is_checkbox_outline(*, width: int, height: int, ink_area: int) -> bool:
    shorter_side = min(width, height)
    longer_side = max(width, height)
    is_checkbox_sized = shorter_side >= MIN_CHECKBOX_SIDE_PX and longer_side <= MAX_CHECKBOX_SIDE_PX
    is_square = longer_side - shorter_side <= longer_side * MAX_CHECKBOX_SIDE_DIFFERENCE_RATIO
    is_hollow = ink_area <= width * height * MAX_CHECKBOX_INK_FILL_RATIO
    return is_checkbox_sized and is_square and is_hollow


def _is_dark_area(box: BoundingBox, gray: np.ndarray) -> bool:
    """Section headings print white on a black bar: no label or answer space sits there."""
    return float(gray[box.y : box.bottom, box.x : box.right].mean()) < DARK_GRAY_LEVEL


def _find_enclosed_regions(rule_mask: np.ndarray) -> list[BoundingBox]:
    """Paper fully surrounded by ruling, other than the page background itself."""
    page_height, page_width = rule_mask.shape[:2]
    closed_rules = cv2.dilate(rule_mask, np.ones((3, 3), np.uint8))
    region_count, _, stats, _ = cv2.connectedComponentsWithStats(cv2.bitwise_not(closed_rules))
    max_area = page_width * page_height * MAX_CELL_PAGE_AREA_FRACTION
    regions = []
    for region in range(1, region_count):
        x, y, width, height, area = (int(value) for value in stats[region])
        touches_page_edge = x == 0 or y == 0 or x + width >= page_width or y + height >= page_height
        if area <= max_area and not touches_page_edge:
            regions.append(BoundingBox(x=x, y=y, width=width, height=height))
    return regions


def _is_cell_sized(region: BoundingBox) -> bool:
    return region.width >= MIN_CELL_WIDTH_PX and region.height >= MIN_CELL_HEIGHT_PX


def _is_character_box_sized(region: BoundingBox) -> bool:
    """Too narrow for a cell, but tall enough to write one character in."""
    is_character_wide = MIN_CHARACTER_BOX_WIDTH_PX <= region.width < MIN_CELL_WIDTH_PX
    return is_character_wide and MIN_CELL_HEIGHT_PX <= region.height <= MAX_CHARACTER_BOX_HEIGHT_PX


def _find_slot_box(
    candidate: LabelCandidate,
    rules: PageRules,
    text_lines: list[TextLine],
    *,
    checkboxes: list[BoundingBox],
    page_width: int,
) -> BoundingBox | None:
    label_cell = _find_containing_cell(candidate.line.box, rules.cells)
    if label_cell is not None:
        return _find_slot_for_label_in_cell(
            candidate, label_cell, rules, text_lines, checkboxes=checkboxes
        )
    box_below = _find_answer_space_in_box_below(candidate.line.box, rules)
    if box_below is not None:
        return box_below
    underline_slot = _find_underline_slot(candidate, rules.underlines, text_lines, rules=rules)
    if underline_slot is not None:
        return underline_slot
    line_above_slot = _find_slot_on_line_above_label(candidate, rules.underlines, text_lines)
    if line_above_slot is not None:
        return line_above_slot
    if not candidate.has_colon:
        return None
    return _find_trailing_space_slot(candidate, text_lines, right_limit=page_width - PAGE_MARGIN_PX)


def _find_slot_for_label_in_cell(
    candidate: LabelCandidate,
    label_cell: BoundingBox,
    rules: PageRules,
    text_lines: list[TextLine],
    *,
    checkboxes: list[BoundingBox],
) -> BoundingBox | None:
    """Inside a table the cell borders are not answer lines: use the next empty cell instead."""
    cell_slot = _find_empty_cell_to_right(label_cell, rules.cells, text_lines)
    if cell_slot is not None:
        return cell_slot
    if not candidate.has_colon:
        return _find_answer_area_in_own_cell(
            candidate, label_cell, rules, text_lines, checkboxes=checkboxes
        )
    return _find_trailing_space_slot(
        candidate, text_lines, right_limit=label_cell.right - CELL_BORDER_INSET_PX
    )


def _find_answer_area_in_own_cell(
    candidate: LabelCandidate,
    label_cell: BoundingBox,
    rules: PageRules,
    text_lines: list[TextLine],
    *,
    checkboxes: list[BoundingBox],
) -> BoundingBox | None:
    """Boxed forms without colons put the answer on a line, below the label, or after a unit."""
    inner_underlines = [
        underline
        for underline in rules.underlines
        if _is_inside_cell_borders(underline, label_cell)
    ]
    underline_slot = _find_underline_slot(candidate, inner_underlines, text_lines, rules=rules)
    if underline_slot is not None:
        return underline_slot
    space_above_lower_line = _find_space_above_lower_line(candidate, inner_underlines, text_lines)
    if space_above_lower_line is not None:
        return space_above_lower_line
    space_below = _find_space_below_text_in_cell(candidate, label_cell, text_lines)
    if space_below is not None and _is_blank(space_below, rules.non_rule_ink):
        return space_below
    if _shares_row_with_other_boxes(label_cell, [*rules.cells, *checkboxes]):
        return None
    space_after = _find_space_after_printed_unit(candidate, label_cell, text_lines)
    if space_after is None or not _is_blank(space_after, rules.non_rule_ink):
        return None
    return space_after


def _find_underline_slot(
    candidate: LabelCandidate,
    underlines: list[BoundingBox],
    text_lines: list[TextLine],
    *,
    rules: PageRules,
) -> BoundingBox | None:
    """Forms with a label column leave a wide gap before the lines, with nothing printed in it;
    a far-off box border is the edge of another part of the page, not this label's line."""
    label_box = candidate.line.box
    slot_left_min = candidate.text_end_x + SLOT_GAP_PX
    matching = [
        underline
        for underline in underlines
        if label_box.y + label_box.height // 2 <= underline.y <= label_box.bottom + label_box.height
        and underline.right - slot_left_min >= MIN_SLOT_WIDTH_PX
        and not _is_edge_of_a_box_not_written_on(underline, rules)
        and (
            underline.x <= candidate.text_end_x + MAX_LABEL_TO_UNDERLINE_GAP_PX
            or _is_open_line_across_label_column(
                candidate, underline, text_lines, cells=rules.cells
            )
        )
    ]
    if not matching:
        return None
    nearest = min(matching, key=lambda underline: abs(underline.x - candidate.text_end_x))
    left = max(nearest.x, slot_left_min)
    slot_height = round(label_box.height * UNDERLINE_SLOT_HEIGHT_RATIO)
    top = _top_below_line_above(nearest, nearest.y - slot_height, underlines)
    slot = BoundingBox(x=left, y=top, width=nearest.right - left, height=nearest.bottom - top)
    return _below_printed_text(slot, text_lines, underlines, label_line=candidate.line)


def _is_printed_within(text_box: BoundingBox, slot: BoundingBox) -> bool:
    """Long printed lines run past the slot's sides, so overlap counts rather than the centre."""
    overlaps_columns = text_box.x < slot.right and slot.x < text_box.right
    shared_height = min(text_box.bottom, slot.bottom) - max(text_box.y, slot.y)
    return overlaps_columns and shared_height * 2 >= text_box.height


def _top_below_line_above(line: BoundingBox, top: int, underlines: list[BoundingBox]) -> int:
    """A slot never reaches past the write-on line above it, which belongs to another answer."""
    lowest_room = line.y - MIN_TEXT_HEIGHT_PX - SLOT_GAP_PX
    lines_above = [
        other.bottom + SLOT_GAP_PX
        for other in underlines
        if max(top, 0) < other.bottom <= lowest_room
        and other.x < line.right
        and line.x < other.right
    ]
    return max([top, 0, *lines_above])


def _below_printed_text(
    slot: BoundingBox,
    text_lines: list[TextLine],
    underlines: list[BoundingBox],
    *,
    label_line: TextLine | None,
) -> BoundingBox | None:
    """Writing goes below any print in the slot; print sitting right on the line means the line
    is pre-filled or underlines a heading, so it leaves no room to write."""
    printed_bottoms = [
        line.box.bottom
        for line in text_lines
        if line is not label_line
        and _is_printed_within(line.box, slot)
        and not _is_hint_on_write_on_line(line.box, underlines)
    ]
    top = max([slot.y, *(bottom + SLOT_GAP_PX for bottom in printed_bottoms)])
    if slot.bottom - top < MIN_WRITING_HEIGHT_PX:
        return None
    return BoundingBox(x=slot.x, y=top, width=slot.width, height=slot.bottom - top)


def _is_open_line_across_label_column(
    candidate: LabelCandidate,
    underline: BoundingBox,
    text_lines: list[TextLine],
    *,
    cells: list[BoundingBox],
) -> bool:
    has_text_between = any(
        line is not candidate.line
        and candidate.text_end_x <= line.box.x < underline.x
        and _share_row(line.box, candidate.line.box)
        for line in text_lines
    )
    return not has_text_between and not _is_cell_border(underline, cells)


def _find_slot_on_line_above_label(
    candidate: LabelCandidate, underlines: list[BoundingBox], text_lines: list[TextLine]
) -> BoundingBox | None:
    """Some forms print the label under its write-on line, starting where the line starts."""
    label_box = candidate.line.box
    lines_above = [
        underline
        for underline in underlines
        if abs(underline.x - label_box.x) <= LINE_END_ALIGNMENT_PX
        and 0 <= label_box.y - underline.bottom <= label_box.height
        and underline.right - label_box.right >= MIN_SLOT_WIDTH_PX
    ]
    if not lines_above:
        return None
    nearest = max(lines_above, key=lambda underline: underline.bottom)
    slot_height = round(label_box.height * UNDERLINE_SLOT_HEIGHT_RATIO)
    top = _top_below_line_above(nearest, nearest.y - slot_height, underlines)
    slot = BoundingBox(x=nearest.x, y=top, width=nearest.width, height=nearest.bottom - top)
    return _below_printed_text(slot, text_lines, underlines, label_line=candidate.line)


def _find_space_above_lower_line(
    candidate: LabelCandidate, inner_underlines: list[BoundingBox], text_lines: list[TextLine]
) -> BoundingBox | None:
    """Date cells print the label at the top and the write-on line lower down, hint below it."""
    label_box = candidate.line.box
    lower_lines = [
        underline
        for underline in inner_underlines
        if underline.y > label_box.bottom + label_box.height
        and _has_hint_under(underline, text_lines)
    ]
    if not lower_lines:
        return None
    nearest = min(lower_lines, key=lambda underline: underline.y)
    top = label_box.bottom + SLOT_GAP_PX
    return BoundingBox(x=nearest.x, y=top, width=nearest.width, height=nearest.bottom - top)


def _has_hint_under(underline: BoundingBox, text_lines: list[TextLine]) -> bool:
    return any(
        line.box.y > underline.y and _is_hint_on_write_on_line(line.box, [underline])
        for line in text_lines
    )


def _find_trailing_space_slot(
    candidate: LabelCandidate, text_lines: list[TextLine], *, right_limit: int
) -> BoundingBox | None:
    label_box = candidate.line.box
    left = candidate.text_end_x + SLOT_GAP_PX
    following_lines = [
        line.box.x
        for line in text_lines
        if line is not candidate.line and line.box.x > left and _share_row(line.box, label_box)
    ]
    right = min([right_limit, *following_lines]) - SLOT_GAP_PX
    if right - left < MIN_SLOT_WIDTH_PX:
        return None
    padding = round(label_box.height * SPACE_SLOT_PADDING_RATIO)
    top = max(label_box.y - padding, 0)
    return BoundingBox(x=left, y=top, width=right - left, height=label_box.bottom + padding - top)


def _find_space_below_text_in_cell(
    candidate: LabelCandidate, label_cell: BoundingBox, text_lines: list[TextLine]
) -> BoundingBox | None:
    """Boxed forms print the label at the top of a box and leave the answer space below it.
    Printed tables centre their text instead, or list several spaced-out lines in one cell."""
    cell_text_boxes = sorted(
        (line.box for line in text_lines if _find_containing_cell(line.box, [label_cell])),
        key=lambda box: box.y,
    )
    if not _is_one_stacked_block(cell_text_boxes):
        return None
    top = max(box.bottom for box in cell_text_boxes) + SLOT_GAP_PX
    bottom = label_cell.bottom - CELL_BORDER_INSET_PX
    space_above_text = cell_text_boxes[0].y - label_cell.y
    space_below_text = bottom - top
    if space_below_text < candidate.line.box.height:
        return None
    if space_below_text < space_above_text * MIN_SPACE_BELOW_TO_ABOVE_LABEL_RATIO:
        return None
    left = label_cell.x + CELL_BORDER_INSET_PX
    return BoundingBox(
        x=left,
        y=top,
        width=label_cell.right - CELL_BORDER_INSET_PX - left,
        height=bottom - top,
    )


def _is_one_stacked_block(boxes_top_down: list[BoundingBox]) -> bool:
    """Lines of one label sit close together; list items are spaced apart."""
    return all(
        lower.y - upper.bottom <= MAX_STACKED_LABEL_LINE_GAP_PX
        for upper, lower in pairwise(boxes_top_down)
    )


def _find_space_after_printed_unit(
    candidate: LabelCandidate, label_cell: BoundingBox, text_lines: list[TextLine]
) -> BoundingBox | None:
    """A unit printed after the label, such as "HKD", means the answer is written after it.
    A row with more print than "label, unit" is a line of a printed table, not a question."""
    printed_on_row = [
        line
        for line in text_lines
        if line is not candidate.line
        and _share_row(line.box, candidate.line.box)
        and _find_containing_cell(line.box, [label_cell]) is not None
    ]
    printed_after_label = [line for line in printed_on_row if line.box.x > candidate.text_end_x]
    if len(printed_on_row) != 1 or len(printed_after_label) != 1:
        return None
    unit = parse_label_candidate(printed_after_label[0])
    if unit is None:
        return None
    return _find_trailing_space_slot(
        unit, text_lines, right_limit=label_cell.right - CELL_BORDER_INSET_PX
    )


def _find_checkbox_label_line(square: BoundingBox, text_lines: list[TextLine]) -> TextLine | None:
    """Bilingual options print one language above the other, so take the top line."""
    square_center_x = square.x + square.width // 2
    max_label_height = square.height * MAX_CHECKBOX_LABEL_HEIGHT_RATIO
    following_lines = [
        line
        for line in text_lines
        if square_center_x < line.box.x <= square.right + MAX_CHECKBOX_LABEL_GAP_PX
        and line.box.height <= max_label_height
        and _share_row(line.box, square)
    ]
    return min(following_lines, key=lambda line: line.box.y, default=None)


def _shares_row_with_other_boxes(label_cell: BoundingBox, boxes: list[BoundingBox]) -> bool:
    return any(box != label_cell and _share_row(box, label_cell) for box in boxes)


def _is_inside_cell_borders(box: BoundingBox, cell: BoundingBox) -> bool:
    is_within_columns = cell.x <= box.x and box.right <= cell.right
    is_between_borders = (
        cell.y + CELL_BORDER_INSET_PX < box.y and box.bottom < cell.bottom - CELL_BORDER_INSET_PX
    )
    return is_within_columns and is_between_borders


def _is_blank(box: BoundingBox, non_rule_ink: np.ndarray) -> bool:
    area = non_rule_ink[box.y : box.bottom, box.x : box.right]
    return np.count_nonzero(area) <= area.size * MAX_BLANK_AREA_INK_FRACTION


def _find_containing_cell(box: BoundingBox, cells: list[BoundingBox]) -> BoundingBox | None:
    center_x = box.x + box.width // 2
    center_y = box.y + box.height // 2
    for cell in cells:
        if cell.x <= center_x <= cell.right and cell.y <= center_y <= cell.bottom:
            return cell
    return None


def _find_empty_cell_to_right(
    label_cell: BoundingBox, cells: list[BoundingBox], text_lines: list[TextLine]
) -> BoundingBox | None:
    candidates = [
        cell
        for cell in cells
        if cell.x >= label_cell.right - CELL_BORDER_INSET_PX * 2
        and _share_row(cell, label_cell)
        and not _contains_text(cell, text_lines)
    ]
    if not candidates:
        return None
    return _inset_cell(min(candidates, key=lambda cell: cell.x))


def _inset_cell(cell: BoundingBox) -> BoundingBox:
    return BoundingBox(
        x=cell.x + CELL_BORDER_INSET_PX,
        y=cell.y + CELL_BORDER_INSET_PX,
        width=max(cell.width - CELL_BORDER_INSET_PX * 2, 1),
        height=max(cell.height - CELL_BORDER_INSET_PX * 2, 1),
    )


def _contains_text(cell: BoundingBox, text_lines: list[TextLine]) -> bool:
    return any(_find_containing_cell(line.box, [cell]) is not None for line in text_lines)


def _share_row(first: BoundingBox, second: BoundingBox) -> bool:
    overlap = min(first.bottom, second.bottom) - max(first.y, second.y)
    return overlap >= SAME_ROW_OVERLAP_RATIO * min(first.height, second.height)


def _overlaps_existing(box: BoundingBox, taken_boxes: list[BoundingBox]) -> bool:
    return any(_overlap_ratio(box, taken) > DUPLICATE_SLOT_OVERLAP_RATIO for taken in taken_boxes)


def _overlap_ratio(first: BoundingBox, second: BoundingBox) -> float:
    overlap_width = min(first.right, second.right) - max(first.x, second.x)
    overlap_height = min(first.bottom, second.bottom) - max(first.y, second.y)
    if overlap_width <= 0 or overlap_height <= 0:
        return 0.0
    smaller_area = min(first.width * first.height, second.width * second.height)
    return overlap_width * overlap_height / smaller_area


def _clip_to_page(box: BoundingBox, *, width: int, height: int) -> BoundingBox:
    right = min(box.right, width)
    bottom = min(box.bottom, height)
    return BoundingBox(x=box.x, y=box.y, width=right - box.x, height=bottom - box.y)


def _display_width(text: str) -> int:
    """Approximate rendered width: CJK characters are about twice as wide as Latin ones."""
    return sum(
        2 if unicodedata.east_asian_width(character) in WIDE_CHARACTER_WIDTHS else 1
        for character in text
    )
