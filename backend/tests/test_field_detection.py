from collections.abc import Callable

import cv2
import numpy as np
import pytest

from app.imaging.page import NORMALISED_PAGE_WIDTH
from app.ocr.types import TextLine
from app.schemas import FIELD_KEY_MAX_LENGTH, FIELD_LABEL_MAX_LENGTH, BoundingBox, FieldType
from app.services.field_detection import (
    MAX_LABEL_ABOVE_BOX_GAP_PX,
    MIN_ANSWER_SPACE_HEIGHT_PX,
    MIN_TICK_BOX_CLEARANCE_PX,
    PAGE_MARGIN_PX,
    DetectedOption,
    DetectedSlot,
    OpenCvFieldDetector,
    detect_field_slots,
    find_printed_text_lines,
    parse_label_candidate,
    refine_detected_slots,
)
from app.services.field_suggestions import (
    guess_field_type,
    suggest_field_key,
    suggest_template_fields,
)
from tests.conftest import (
    NAME_UNDERLINE_LEFT,
    NAME_UNDERLINE_RIGHT,
    NAME_UNDERLINE_Y,
    FakeCropReader,
)

PAGE_HEIGHT = 1200
BLACK = (0, 0, 0)
TABLE_TOP = 500
TABLE_ROW_HEIGHT = 100
TABLE_LEFT = 100
TABLE_SPLIT = 600
TABLE_RIGHT = 1400
BOX_TOP = 300
BOX_BOTTOM = 450
SINGLE_ROW_BOX_BOTTOM = 370
DASHED_LINE_Y = 420
DASH_LENGTH_PX = 6
DASH_PERIOD_PX = 11
CHECKBOX_SIDE_PX = 34
PATTERN_BLOCK_PX = 8
PATTERN_COLUMNS = 12
PATTERN_ROWS = 10


def blank_page() -> np.ndarray:
    return np.full((PAGE_HEIGHT, NORMALISED_PAGE_WIDTH, 3), 255, dtype=np.uint8)


def draw_two_row_table(page: np.ndarray) -> None:
    for row in range(2):
        top = TABLE_TOP + row * TABLE_ROW_HEIGHT
        cv2.rectangle(page, (TABLE_LEFT, top), (TABLE_SPLIT, top + TABLE_ROW_HEIGHT), BLACK, 3)
        cv2.rectangle(page, (TABLE_SPLIT, top), (TABLE_RIGHT, top + TABLE_ROW_HEIGHT), BLACK, 3)


def text_line(text: str, *, x: int, y: int, width: int, height: int = 40) -> TextLine:
    return TextLine(
        text=text, confidence=0.99, box=BoundingBox(x=x, y=y, width=width, height=height)
    )


def draw_dashed_line(page: np.ndarray, *, y: int, left: int, right: int) -> None:
    for dash_left in range(left, right - DASH_LENGTH_PX, DASH_PERIOD_PX):
        cv2.line(page, (dash_left, y), (dash_left + DASH_LENGTH_PX - 1, y), BLACK, 2)


def draw_checkbox(page: np.ndarray, *, x: int, y: int) -> None:
    cv2.rectangle(page, (x, y), (x + CHECKBOX_SIDE_PX, y + CHECKBOX_SIDE_PX), BLACK, 2)


def draw_qr_like_pattern(page: np.ndarray, *, x: int, y: int) -> None:
    for row in range(PATTERN_ROWS):
        for column in range(PATTERN_COLUMNS):
            if (row + column) % 2 == 0:
                block_x = x + column * PATTERN_BLOCK_PX
                block_y = y + row * PATTERN_BLOCK_PX
                cv2.rectangle(
                    page,
                    (block_x, block_y),
                    (block_x + PATTERN_BLOCK_PX - 1, block_y + PATTERN_BLOCK_PX - 1),
                    BLACK,
                    cv2.FILLED,
                )


def draw_single_row_box(page: np.ndarray) -> None:
    cv2.rectangle(page, (TABLE_LEFT, BOX_TOP), (TABLE_RIGHT, SINGLE_ROW_BOX_BOTTOM), BLACK, 3)


def test_label_followed_by_underline_gets_slot_above_the_line(
    blank_form: np.ndarray, name_label_line: TextLine
) -> None:
    slots = detect_field_slots(blank_form, [name_label_line])

    assert len(slots) == 1
    slot = slots[0]
    assert slot.label == "Name"
    assert slot.box.x >= NAME_UNDERLINE_LEFT - 5
    assert slot.box.right == pytest.approx(NAME_UNDERLINE_RIGHT, abs=5)
    assert slot.box.y < NAME_UNDERLINE_Y < slot.box.bottom + 5


def test_label_in_table_cell_gets_the_empty_cell_to_its_right() -> None:
    page = blank_page()
    draw_two_row_table(page)
    labels = [
        text_line("雇主 Employer", x=120, y=TABLE_TOP + 30, width=250),
        text_line("月薪 Salary", x=120, y=TABLE_TOP + TABLE_ROW_HEIGHT + 30, width=220),
    ]

    slots = detect_field_slots(page, labels)

    assert [slot.label for slot in slots] == ["雇主 Employer", "月薪 Salary"]
    first_cell = slots[0].box
    assert first_cell.x == pytest.approx(TABLE_SPLIT, abs=8)
    assert first_cell.right == pytest.approx(TABLE_RIGHT, abs=8)
    assert first_cell.y == pytest.approx(TABLE_TOP, abs=8)


def test_label_in_cell_whose_neighbour_has_text_uses_space_inside_its_own_cell() -> None:
    page = blank_page()
    draw_two_row_table(page)
    labels = [
        text_line("Ref:", x=120, y=TABLE_TOP + 30, width=80),
        text_line("Printed value", x=640, y=TABLE_TOP + 30, width=300),
    ]

    slots = detect_field_slots(page, labels)

    assert len(slots) == 1
    assert slots[0].label == "Ref"
    assert slots[0].box.right <= TABLE_SPLIT


def test_label_in_cell_without_colon_or_empty_neighbour_is_ignored() -> None:
    page = blank_page()
    draw_two_row_table(page)
    labels = [
        text_line("Item", x=120, y=TABLE_TOP + 30, width=80),
        text_line("Amount", x=640, y=TABLE_TOP + 30, width=150),
    ]

    assert detect_field_slots(page, labels) == []


def test_label_at_top_of_box_gets_the_empty_space_below_it() -> None:
    page = blank_page()
    cv2.rectangle(page, (TABLE_LEFT, BOX_TOP), (TABLE_RIGHT, BOX_BOTTOM), BLACK, 3)
    labels = [text_line("Bank Name 銀行名稱", x=120, y=BOX_TOP + 10, width=300)]

    slots = detect_field_slots(page, labels)

    assert len(slots) == 1
    slot = slots[0].box
    assert slots[0].label == "Bank Name 銀行名稱"
    assert slot.y > BOX_TOP + 50
    assert slot.bottom == pytest.approx(BOX_BOTTOM, abs=8)
    assert slot.x == pytest.approx(TABLE_LEFT, abs=8)
    assert slot.right == pytest.approx(TABLE_RIGHT, abs=8)


def test_two_line_label_in_box_gets_one_slot_below_its_last_line() -> None:
    page = blank_page()
    cv2.rectangle(page, (TABLE_LEFT, BOX_TOP), (TABLE_RIGHT, BOX_BOTTOM), BLACK, 3)
    labels = [
        text_line("Account No. (Exclude Bank No.)", x=120, y=BOX_TOP + 10, width=500),
        text_line("帳戶號碼 (不包括銀行編號)", x=120, y=BOX_TOP + 55, width=400),
    ]

    slots = detect_field_slots(page, labels)

    assert len(slots) == 1
    assert slots[0].label == "Account No. (Exclude Bank No.)"
    assert slots[0].box.y > BOX_TOP + 95


def test_side_by_side_boxes_each_get_the_space_below_their_own_label() -> None:
    page = blank_page()
    cv2.rectangle(page, (TABLE_LEFT, BOX_TOP), (TABLE_SPLIT, BOX_BOTTOM), BLACK, 3)
    cv2.rectangle(page, (TABLE_SPLIT, BOX_TOP), (TABLE_RIGHT, BOX_BOTTOM), BLACK, 3)
    labels = [
        text_line("Bank No. 銀行編號", x=120, y=BOX_TOP + 10, width=250),
        text_line("Branch No. 分行號碼", x=TABLE_SPLIT + 20, y=BOX_TOP + 10, width=250),
    ]

    slots = detect_field_slots(page, labels)

    assert [slot.label for slot in slots] == ["Bank No. 銀行編號", "Branch No. 分行號碼"]
    assert slots[0].box.right <= TABLE_SPLIT
    assert slots[1].box.x >= TABLE_SPLIT
    assert all(slot.box.y > BOX_TOP + 50 for slot in slots)


def test_dashed_line_closes_the_box_above_it() -> None:
    page = blank_page()
    cv2.rectangle(page, (TABLE_LEFT, BOX_TOP), (TABLE_RIGHT, DASHED_LINE_Y + 110), BLACK, 3)
    draw_dashed_line(page, y=DASHED_LINE_Y, left=TABLE_LEFT + 6, right=TABLE_RIGHT - 6)
    labels = [
        text_line("Bank No. 銀行編號", x=120, y=BOX_TOP + 10, width=250),
        text_line("Note the 3-digit Bank No. identifies your bank", x=120, y=430, width=1200),
        text_line("Please complete the Bank No. accurately", x=120, y=470, width=1100),
    ]

    slots = detect_field_slots(page, labels)

    assert [slot.label for slot in slots] == ["Bank No. 銀行編號"]
    assert slots[0].box.bottom == pytest.approx(DASHED_LINE_Y, abs=8)


def test_label_in_box_uses_the_write_on_line_beside_it() -> None:
    page = blank_page()
    draw_single_row_box(page)
    cv2.line(page, (400, BOX_TOP + 50), (1000, BOX_TOP + 50), BLACK, 2)
    labels = [text_line("Document No.", x=120, y=BOX_TOP + 12, width=200, height=30)]

    slots = detect_field_slots(page, labels)

    assert len(slots) == 1
    assert slots[0].box.x == pytest.approx(400, abs=8)
    assert slots[0].box.right == pytest.approx(1000, abs=8)


def test_label_in_box_followed_by_a_unit_gets_the_space_after_the_unit() -> None:
    page = blank_page()
    draw_single_row_box(page)
    labels = [
        text_line("Upper Limit", x=120, y=BOX_TOP + 12, width=250, height=30),
        text_line("HKD", x=500, y=BOX_TOP + 12, width=80, height=30),
    ]

    slots = detect_field_slots(page, labels)

    assert [slot.label for slot in slots] == ["Upper Limit"]
    assert slots[0].box.x > 580
    assert slots[0].box.right <= TABLE_RIGHT


def test_label_in_box_followed_only_by_fill_characters_is_not_a_field() -> None:
    page = blank_page()
    draw_single_row_box(page)
    labels = [
        text_line("Upper Limit", x=120, y=BOX_TOP + 12, width=250, height=30),
        text_line("______", x=500, y=BOX_TOP + 12, width=80, height=30),
    ]

    assert detect_field_slots(page, labels) == []


def test_row_of_tick_boxes_gets_no_text_field_after_the_options() -> None:
    page = blank_page()
    draw_single_row_box(page)
    draw_checkbox(page, x=500, y=BOX_TOP + 18)
    labels = [
        text_line("Account Type", x=120, y=BOX_TOP + 20, width=250, height=30),
        text_line("Personal", x=545, y=BOX_TOP + 20, width=120, height=30),
    ]

    slots = detect_field_slots(page, labels)

    assert [(slot.field_type, slot.box) for slot in slots] == [
        (FieldType.CHOICE, slots[0].options[0].box)
    ]
    assert [option.label for option in slots[0].options] == ["Personal"]


def test_space_below_label_with_printed_pattern_is_not_a_field() -> None:
    page = blank_page()
    cv2.rectangle(page, (TABLE_LEFT, BOX_TOP), (TABLE_SPLIT, BOX_BOTTOM), BLACK, 3)
    draw_qr_like_pattern(page, x=TABLE_LEFT + 100, y=BOX_TOP + 60)
    labels = [text_line("Internal use only", x=120, y=BOX_TOP + 10, width=250)]

    assert detect_field_slots(page, labels) == []


def test_label_above_a_page_wide_divider_is_not_a_field() -> None:
    page = blank_page()
    cv2.line(page, (40, 300), (NORMALISED_PAGE_WIDTH - 40, 300), BLACK, 3)
    labels = [text_line("ct", x=500, y=150, width=240, height=170)]

    assert detect_field_slots(page, labels) == []


def test_lone_tick_box_becomes_a_choice_with_one_option() -> None:
    page = blank_page()
    draw_checkbox(page, x=200, y=300)
    labels = [text_line("Personal 個人", x=245, y=305, width=150, height=25)]

    [slot] = detect_field_slots(page, labels)

    assert slot.field_type is FieldType.CHOICE
    [option] = slot.options
    assert option.label == "Personal 個人"
    assert option.box.x == pytest.approx(200, abs=3)
    assert option.box.width == pytest.approx(CHECKBOX_SIDE_PX, abs=3)
    assert slot.box == option.box


def test_tick_boxes_in_one_cell_become_one_choice_in_reading_order() -> None:
    page = blank_page()
    cv2.rectangle(page, (TABLE_LEFT, BOX_TOP), (TABLE_RIGHT, BOX_BOTTOM), BLACK, 3)
    draw_checkbox(page, x=700, y=BOX_TOP + 21)
    draw_checkbox(page, x=200, y=BOX_TOP + 20)
    draw_checkbox(page, x=200, y=BOX_TOP + 90)
    draw_checkbox(page, x=200, y=900)
    labels = [
        text_line("Account Type", x=120, y=BOX_TOP + 22, width=70, height=25),
        text_line("Joint", x=745, y=BOX_TOP + 23, width=100, height=25),
        text_line("Personal", x=245, y=BOX_TOP + 22, width=120, height=25),
        text_line("Corporate", x=245, y=BOX_TOP + 92, width=140, height=25),
        text_line("Remarks", x=245, y=902, width=120, height=25),
    ]

    slots = detect_field_slots(page, labels)

    assert [[option.label for option in slot.options] for slot in slots] == [
        ["Personal", "Joint", "Corporate"],
        ["Remarks"],
    ]
    assert [slot.label for slot in slots] == ["Account Type", ""]
    assert all(slot.field_type is FieldType.CHOICE for slot in slots)
    assert slots[0].box.x == slots[0].options[0].box.x
    assert slots[0].box.right == slots[0].options[1].box.right
    assert slots[0].box.bottom == slots[0].options[2].box.bottom


def test_square_shaped_character_beside_other_print_is_not_a_tick_box() -> None:
    page = blank_page()
    draw_checkbox(page, x=200, y=300)
    neighbour_left = 200 + CHECKBOX_SIDE_PX + MIN_TICK_BOX_CLEARANCE_PX // 2
    cv2.rectangle(page, (neighbour_left, 305), (neighbour_left + 20, 330), BLACK, cv2.FILLED)
    labels = [text_line("口語", x=245, y=305, width=60, height=25)]

    assert detect_field_slots(page, labels) == []


def test_tick_box_label_is_the_top_line_of_bilingual_option_text() -> None:
    page = blank_page()
    draw_checkbox(page, x=200, y=300)
    labels = [
        text_line("Passport", x=245, y=298, width=120, height=20),
        text_line("護照", x=243, y=322, width=50, height=25),
    ]

    slots = detect_field_slots(page, labels)

    assert [option.label for slot in slots for option in slot.options] == ["Passport"]


@pytest.mark.parametrize(
    "labels",
    [
        pytest.param([], id="no text beside it"),
        pytest.param([text_line("ct", x=245, y=240, width=240, height=170)], id="logo text"),
        pytest.param([text_line("OK", x=190, y=295, width=300, height=45)], id="printed letter"),
        pytest.param([text_line("______", x=245, y=305, width=150, height=25)], id="fill only"),
    ],
)
def test_square_that_is_not_a_tick_box_is_ignored(labels: list[TextLine]) -> None:
    page = blank_page()
    draw_checkbox(page, x=200, y=300)

    assert detect_field_slots(page, labels) == []


def test_colon_label_without_rules_gets_space_until_next_text() -> None:
    labels = [
        text_line("签署日期 Signed Date:", x=100, y=900, width=360),
        text_line("Page 1", x=1300, y=905, width=120),
    ]

    slots = detect_field_slots(blank_page(), labels)

    assert len(slots) == 1
    assert slots[0].box.x > 460
    assert slots[0].box.right < 1300


def test_colon_label_slot_extends_to_page_margin_when_row_is_empty() -> None:
    slots = detect_field_slots(blank_page(), [text_line("Remarks:", x=100, y=900, width=150)])

    assert slots[0].box.right == NORMALISED_PAGE_WIDTH - PAGE_MARGIN_PX - 6


def test_headings_and_cramped_labels_are_not_fields() -> None:
    labels = [
        text_line("APPLICATION FORM", x=100, y=80, width=600),
        text_line("Tel:", x=100, y=900, width=60),
        text_line("Fax", x=200, y=900, width=60),
    ]

    assert detect_field_slots(blank_page(), labels) == []


def test_two_labels_sharing_one_underline_produce_one_slot(blank_form: np.ndarray) -> None:
    labels = [
        text_line("Name:", x=100, y=200, width=200),
        text_line("Name:", x=105, y=202, width=200),
    ]

    assert len(detect_field_slots(blank_form, labels)) == 1


def test_label_end_skips_underscores_inside_ocr_box() -> None:
    candidate = parse_label_candidate(text_line("Name:_____", x=100, y=0, width=200))

    assert candidate is not None
    assert candidate.label == "Name"
    assert candidate.has_colon
    assert candidate.text_end_x == 200


def test_fill_characters_only_is_not_a_label() -> None:
    assert parse_label_candidate(text_line("______", x=0, y=0, width=100)) is None


def test_unread_text_line_is_an_unnamed_label_ending_at_its_box() -> None:
    candidate = parse_label_candidate(text_line("", x=100, y=0, width=200))

    assert candidate is not None
    assert candidate.label == ""
    assert not candidate.has_colon
    assert candidate.text_end_x == 300


def test_finds_printed_text_lines_but_not_tick_boxes_thin_strokes_or_tall_marks() -> None:
    page = blank_page()
    cv2.putText(page, "Name", (100, 235), cv2.FONT_HERSHEY_SIMPLEX, 1.2, BLACK, 3)
    draw_checkbox(page, x=100 - 12 - CHECKBOX_SIDE_PX, y=200)
    cv2.line(page, (600, 210), (600, 225), BLACK, 2)
    draw_qr_like_pattern(page, x=900, y=150)

    [line] = find_printed_text_lines(page)

    assert line.text == ""
    assert line.box.x == pytest.approx(100, abs=3)
    assert line.box.bottom == pytest.approx(235, abs=5)


def test_opencv_detector_names_a_choice_and_each_of_its_options() -> None:
    page = blank_page()
    draw_single_row_box(page)
    cv2.putText(page, "Type", (120, BOX_TOP + 45), cv2.FONT_HERSHEY_SIMPLEX, 1, BLACK, 2)
    draw_checkbox(page, x=500, y=BOX_TOP + 18)
    cv2.putText(page, "Yes", (550, BOX_TOP + 45), cv2.FONT_HERSHEY_SIMPLEX, 1, BLACK, 2)
    draw_checkbox(page, x=200, y=900)
    cv2.putText(page, "No", (250, 927), cv2.FONT_HERSHEY_SIMPLEX, 1, BLACK, 2)
    label_reader = make_label_reader("Read")

    slots = OpenCvFieldDetector(label_reader=label_reader).detect_fields(page)

    assert [(slot.label, [option.label for option in slot.options]) for slot in slots] == [
        ("Read", ["Read"]),
        ("", ["Read"]),
    ]
    assert label_reader.call_count == 3


def test_long_label_reading_is_cut_to_the_template_limit(blank_form: np.ndarray) -> None:
    detector = OpenCvFieldDetector(label_reader=make_label_reader("Note " * 100))

    [slot] = detector.detect_fields(blank_form)

    assert len(slot.label) == FIELD_LABEL_MAX_LENGTH


def make_label_reader(text: str) -> FakeCropReader:
    return FakeCropReader(name="label-reader", text=text, confidence=0.9)


def test_opencv_detector_reads_only_the_label_of_each_field(blank_form: np.ndarray) -> None:
    label_reader = make_label_reader("Name:_____")

    [slot] = OpenCvFieldDetector(label_reader=label_reader).detect_fields(blank_form)

    assert slot.label == "Name"
    assert label_reader.call_count == 1
    assert slot.box.x >= NAME_UNDERLINE_LEFT - 5
    assert slot.box.right == pytest.approx(NAME_UNDERLINE_RIGHT, abs=5)
    assert slot.box.y < NAME_UNDERLINE_Y < slot.box.bottom + 5


@pytest.mark.parametrize(
    ("label", "expected_key"),
    [
        ("姓名 Full Name", "full_name"),
        ("Date of Birth (DD/MM/YYYY)", "date_of_birth_dd_mm_yyyy"),
        ("2. Employer", "employer"),
        ("姓名", "field_1"),
    ],
)
def test_suggests_snake_case_key_from_english_words(label: str, expected_key: str) -> None:
    assert suggest_field_key(label, set()) == expected_key


def test_suggested_keys_are_unique() -> None:
    assert suggest_field_key("Phone", {"phone", "phone_2"}) == "phone_3"
    assert suggest_field_key("地址", {"field_1"}) == "field_2"


def test_numbered_key_for_a_long_duplicate_label_stays_within_max_length() -> None:
    long_label = "Passport (applicable only to applicants without an HKID card) " * 2
    first_key = suggest_field_key(long_label, set())

    second_key = suggest_field_key(long_label, {first_key})

    assert len(first_key) == FIELD_KEY_MAX_LENGTH
    assert len(second_key) <= FIELD_KEY_MAX_LENGTH
    assert second_key.endswith("_2")
    assert second_key != first_key


@pytest.mark.parametrize(
    ("label", "expected_type"),
    [
        ("出生日期 Date of Birth", FieldType.DATE),
        ("电话 Phone", FieldType.NUMBER),
        ("月薪 Monthly Salary", FieldType.NUMBER),
        ("地址 Address", FieldType.TEXT),
    ],
)
def test_guesses_field_type_from_label(label: str, expected_type: FieldType) -> None:
    assert guess_field_type(label) is expected_type


def test_suggest_template_fields_assigns_ids_keys_and_types(
    blank_form: np.ndarray, name_label_line: TextLine
) -> None:
    slots = detect_field_slots(blank_form, [name_label_line])

    fields = suggest_template_fields([[*slots, *slots]])

    assert [field.key for field in fields] == ["name", "name_2"]
    assert fields[0].id != fields[1].id
    assert fields[0].field_type is FieldType.TEXT


def test_suggested_fields_record_their_page_and_keys_stay_unique_across_pages(
    blank_form: np.ndarray, name_label_line: TextLine
) -> None:
    slots = detect_field_slots(blank_form, [name_label_line])

    fields = suggest_template_fields([slots, [], slots])

    assert [(field.key, field.page_index) for field in fields] == [("name", 0), ("name_2", 2)]


def test_suggested_choice_keeps_each_option_label_and_square() -> None:
    personal = DetectedOption(
        label="Personal 個人", box=BoundingBox(x=10, y=10, width=30, height=30)
    )
    joint = DetectedOption(label="Joint 聯名", box=BoundingBox(x=200, y=10, width=30, height=30))
    slot = DetectedSlot(
        label="Bank Account Type 銀行帳戶類別",
        box=BoundingBox(x=10, y=10, width=220, height=30),
        field_type=FieldType.CHOICE,
        options=(personal, joint),
    )

    [field] = suggest_template_fields([[slot]])

    assert field.key == "bank_account_type"
    assert field.field_type is FieldType.CHOICE
    assert [(option.label, option.box) for option in field.options] == [
        (personal.label, personal.box),
        (joint.label, joint.box),
    ]
    assert field.options[0].id != field.options[1].id


def test_detector_field_type_overrides_the_keyword_guess() -> None:
    slot = DetectedSlot(
        label="Phone 電話",
        box=BoundingBox(x=10, y=10, width=200, height=40),
        field_type=FieldType.TEXT,
    )

    fields = suggest_template_fields([[slot]])

    assert fields[0].field_type is FieldType.TEXT


SIGNATURE_LABEL_BOX = BoundingBox(x=TABLE_LEFT + 10, y=BOX_TOP + 8, width=400, height=34)


def draw_signature_cell(page: np.ndarray) -> None:
    cv2.rectangle(page, (TABLE_LEFT, BOX_TOP), (TABLE_SPLIT, BOX_BOTTOM), BLACK, 3)
    cv2.putText(
        page, "Signature", (TABLE_LEFT + 15, BOX_TOP + 35), cv2.FONT_HERSHEY_SIMPLEX, 1, BLACK, 2
    )


def draw_cell_filled_with_print(page: np.ndarray) -> None:
    draw_signature_cell(page)
    draw_qr_like_pattern(page, x=TABLE_LEFT + 100, y=BOX_TOP + 60)


def test_box_on_a_cell_label_grows_into_the_empty_space_below_it() -> None:
    page = blank_page()
    draw_signature_cell(page)
    slot = DetectedSlot(label="Signature", box=SIGNATURE_LABEL_BOX)

    [refined] = refine_detected_slots(page, [slot])

    assert refined.box.y >= SIGNATURE_LABEL_BOX.bottom
    assert refined.box.bottom == pytest.approx(BOX_BOTTOM, abs=10)
    assert refined.box.x == pytest.approx(TABLE_LEFT, abs=10)
    assert refined.box.right == pytest.approx(TABLE_SPLIT, abs=10)
    assert refined.box.height >= MIN_ANSWER_SPACE_HEIGHT_PX


def test_answer_space_stops_at_printed_text_lower_in_the_cell() -> None:
    page = blank_page()
    draw_signature_cell(page)
    hint_baseline_y = BOX_BOTTOM - 8
    (_, hint_height), _ = cv2.getTextSize("DD / MM / YYYY", cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
    printed_hint_top = hint_baseline_y - hint_height
    cv2.putText(
        page,
        "DD / MM / YYYY",
        (TABLE_LEFT + 15, hint_baseline_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        BLACK,
        2,
    )
    slot = DetectedSlot(label="Date", box=SIGNATURE_LABEL_BOX)

    [refined] = refine_detected_slots(page, [slot])

    assert refined.box.y >= SIGNATURE_LABEL_BOX.bottom
    assert refined.box.bottom <= printed_hint_top


@pytest.mark.parametrize(
    "draw_page",
    [
        pytest.param(lambda page: None, id="not inside a cell"),
        pytest.param(draw_single_row_box, id="cell too short for an answer below the label"),
        pytest.param(draw_cell_filled_with_print, id="space below the label is printed on"),
    ],
)
def test_box_without_empty_cell_space_below_is_kept(
    draw_page: Callable[[np.ndarray], None],
) -> None:
    page = blank_page()
    draw_page(page)
    slot = DetectedSlot(label="Name", box=SIGNATURE_LABEL_BOX)

    assert refine_detected_slots(page, [slot]) == [slot]


def test_choice_options_snap_onto_the_nearest_tick_squares() -> None:
    page = blank_page()
    draw_checkbox(page, x=200, y=300)
    draw_checkbox(page, x=500, y=300)
    personal = DetectedOption(label="Personal", box=BoundingBox(x=245, y=305, width=150, height=25))
    joint = DetectedOption(label="Joint", box=BoundingBox(x=545, y=305, width=120, height=25))
    remarks = DetectedOption(label="Remarks", box=BoundingBox(x=900, y=900, width=30, height=30))
    slot = DetectedSlot(
        label="Account Type",
        box=BoundingBox(x=200, y=300, width=700, height=630),
        field_type=FieldType.CHOICE,
        options=(personal, joint, remarks),
    )

    [refined] = refine_detected_slots(page, [slot])

    personal_box, joint_box, remarks_box = (option.box for option in refined.options)
    assert personal_box.x == pytest.approx(200, abs=3)
    assert personal_box.width == pytest.approx(CHECKBOX_SIDE_PX, abs=3)
    assert joint_box.x == pytest.approx(500, abs=3)
    assert remarks_box == remarks.box
    assert refined.box.x == personal_box.x
    assert refined.box.bottom == remarks_box.bottom


TALL_BOX_BOTTOM = BOX_TOP + 250
LABEL_HEIGHT = 30
PAGE_WIDE_BOX_RIGHT = NORMALISED_PAGE_WIDTH - TABLE_LEFT


def draw_box_with_label_above(
    page: np.ndarray, *, gap: int, box_bottom: int, box_right: int = TABLE_SPLIT
) -> list[TextLine]:
    cv2.rectangle(page, (TABLE_LEFT, BOX_TOP), (box_right, box_bottom), BLACK, 3)
    label_top = BOX_TOP - gap - LABEL_HEIGHT
    return [text_line("Signature", x=120, y=label_top, width=200, height=LABEL_HEIGHT)]


def test_label_just_above_a_box_gets_the_empty_box_rather_than_its_top_border() -> None:
    page = blank_page()
    labels = draw_box_with_label_above(page, gap=10, box_bottom=TALL_BOX_BOTTOM)

    [slot] = detect_field_slots(page, labels)

    assert slot.label == "Signature"
    assert slot.box.x == pytest.approx(TABLE_LEFT, abs=8)
    assert slot.box.right == pytest.approx(TABLE_SPLIT, abs=8)
    assert slot.box.y == pytest.approx(BOX_TOP, abs=8)
    assert slot.box.bottom == pytest.approx(TALL_BOX_BOTTOM, abs=8)


def test_label_above_a_box_with_a_printed_date_hint_gets_the_space_above_the_hint() -> None:
    page = blank_page()
    labels = draw_box_with_label_above(page, gap=10, box_bottom=TALL_BOX_BOTTOM)
    hint_baseline_y = TALL_BOX_BOTTOM - 10
    (_, hint_height), _ = cv2.getTextSize("DD / MM / YYYY", cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
    cv2.putText(
        page,
        "DD / MM / YYYY",
        (TABLE_LEFT + 15, hint_baseline_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        BLACK,
        2,
    )

    [slot] = detect_field_slots(page, labels)

    assert slot.box.y == pytest.approx(BOX_TOP, abs=8)
    assert slot.box.bottom <= hint_baseline_y - hint_height


@pytest.mark.parametrize(
    ("gap", "box_bottom"),
    [
        pytest.param(MAX_LABEL_ABOVE_BOX_GAP_PX + 10, TALL_BOX_BOTTOM, id="label too far above"),
        pytest.param(10, BOX_TOP + MIN_ANSWER_SPACE_HEIGHT_PX // 2, id="box too short"),
    ],
)
def test_label_above_a_box_is_ignored_when_far_away_or_without_room(
    gap: int, box_bottom: int
) -> None:
    page = blank_page()
    labels = draw_box_with_label_above(
        page, gap=gap, box_bottom=box_bottom, box_right=PAGE_WIDE_BOX_RIGHT
    )

    assert detect_field_slots(page, labels) == []


def draw_text_block(page: np.ndarray, *, x: int, y: int, height: int) -> None:
    """A slanted stroke inks every row of the text's height without looking like a ruled line."""
    cv2.line(page, (x, y), (x + 30, y + height), BLACK, 2)


def test_tick_box_with_its_option_text_close_beside_it_is_still_a_tick_box() -> None:
    page = blank_page()
    draw_checkbox(page, x=200, y=300)
    draw_text_block(page, x=200 + CHECKBOX_SIDE_PX + 7, y=308, height=19)
    labels = [text_line("HKID Card", x=241, y=308, width=150, height=19)]

    [slot] = detect_field_slots(page, labels)

    assert [option.label for option in slot.options] == ["HKID Card"]


def test_square_starting_a_line_of_text_as_tall_as_itself_is_not_a_tick_box() -> None:
    page = blank_page()
    draw_checkbox(page, x=200, y=300)
    draw_text_block(page, x=200 + CHECKBOX_SIDE_PX + 7, y=300, height=CHECKBOX_SIDE_PX)
    labels = [text_line("口語", x=241, y=300, width=60, height=CHECKBOX_SIDE_PX)]

    assert detect_field_slots(page, labels) == []


def test_tick_boxes_on_one_open_row_become_one_choice_named_by_the_question_on_their_left() -> None:
    page = blank_page()
    for box_x in (400, 600, 800):
        draw_checkbox(page, x=box_x, y=300)
    labels = [
        text_line("Title", x=100, y=305, width=150, height=25),
        text_line("Mr", x=445, y=305, width=60, height=25),
        text_line("Ms", x=645, y=305, width=60, height=25),
        text_line("Dr", x=845, y=305, width=60, height=25),
    ]

    [slot] = detect_field_slots(page, labels)

    assert slot.label == "Title"
    assert [option.label for option in slot.options] == ["Mr", "Ms", "Dr"]


def test_tick_boxes_stacked_under_a_question_form_one_choice_until_the_next_question() -> None:
    page = blank_page()
    for box_y in (300, 400, 500, 640):
        draw_checkbox(page, x=120, y=box_y)
    labels = [
        text_line("My Tax Residence is", x=100, y=250, width=400, height=25),
        text_line("(i)", x=165, y=305, width=40, height=25),
        text_line("(ii)", x=165, y=405, width=40, height=25),
        text_line("(iii)", x=165, y=505, width=40, height=25),
        text_line("Do you agree", x=100, y=590, width=300, height=25),
        text_line("Yes", x=165, y=645, width=60, height=25),
    ]

    slots = detect_field_slots(page, labels)

    assert [(slot.label, [option.label for option in slot.options]) for slot in slots] == [
        ("My Tax Residence is", ["(i)", "(ii)", "(iii)"]),
        ("Do you agree", ["Yes"]),
    ]


def test_question_above_a_row_of_tick_boxes_includes_its_english_line_above_the_chinese() -> None:
    page = blank_page()
    for box_x in (400, 600):
        draw_checkbox(page, x=box_x, y=300)
    english_line = text_line("District Area", x=100, y=230, width=150, height=25)
    chinese_line = text_line("區域", x=100, y=258, width=60, height=25)
    labels = [
        english_line,
        chinese_line,
        text_line("Hong Kong", x=445, y=305, width=120, height=25),
        text_line("Kowloon", x=645, y=305, width=120, height=25),
    ]

    [slot] = detect_field_slots(page, labels)

    assert slot.label == "區域"
    assert slot.label_box is not None
    assert slot.label_box.y == english_line.box.y
    assert slot.label_box.bottom == chinese_line.box.bottom


def test_two_line_label_in_a_label_column_gets_the_distant_line_on_its_row() -> None:
    page = blank_page()
    cv2.line(page, (500, 330), (1400, 330), BLACK, 2)
    english_line = text_line("Flat / Room", x=100, y=280, width=150, height=20)
    chinese_line = text_line("單位", x=100, y=304, width=100, height=22)

    [slot] = detect_field_slots(page, [english_line, chinese_line])

    assert slot.box.x == pytest.approx(500, abs=8)
    assert slot.box.right == pytest.approx(1400, abs=8)
    assert slot.label_box is not None
    assert slot.label_box.y == english_line.box.y
    assert slot.label_box.bottom == chinese_line.box.bottom


def test_distant_line_goes_to_the_text_printed_just_before_it() -> None:
    page = blank_page()
    cv2.line(page, (700, 330), (1400, 330), BLACK, 2)
    labels = [
        text_line("Flat / Room", x=100, y=304, width=150, height=22),
        text_line("Floor", x=550, y=304, width=80, height=22),
    ]

    [slot] = detect_field_slots(page, labels)

    assert slot.label == "Floor"


def test_distant_box_border_on_the_label_row_is_not_its_write_on_line() -> None:
    page = blank_page()
    cv2.rectangle(page, (900, 200), (1400, 330), BLACK, 3)
    labels = [text_line("Direct Debit Authorization", x=100, y=300, width=300, height=25)]

    assert detect_field_slots(page, labels) == []


def test_separator_printed_on_a_write_on_line_is_not_a_label() -> None:
    page = blank_page()
    cv2.line(page, (400, 330), (1000, 330), BLACK, 2)
    labels = [
        text_line("/", x=550, y=298, width=15, height=30),
        text_line("Date of Birth", x=100, y=300, width=200, height=25),
    ]

    [slot] = detect_field_slots(page, labels)

    assert slot.label == "Date of Birth"
    assert slot.box.x == pytest.approx(400, abs=8)


@pytest.mark.parametrize(
    ("label_width", "expected_slot_count"),
    [
        pytest.param(100, 1, id="label under a longer line"),
        pytest.param(560, 0, id="heading as wide as the line above it"),
    ],
)
def test_label_printed_under_its_write_on_line_gets_the_space_above_the_line(
    label_width: int, expected_slot_count: int
) -> None:
    page = blank_page()
    cv2.line(page, (900, 400), (1500, 400), BLACK, 2)
    labels = [text_line("Name", x=900, y=410, width=label_width, height=22)]

    slots = detect_field_slots(page, labels)

    assert len(slots) == expected_slot_count
    for slot in slots:
        assert slot.box.x == pytest.approx(900, abs=8)
        assert slot.box.right == pytest.approx(1500, abs=8)
        assert slot.box.bottom == pytest.approx(402, abs=4)


def test_date_cell_gets_the_space_above_its_write_on_line_not_after_the_hint() -> None:
    page = blank_page()
    cv2.rectangle(page, (TABLE_LEFT, BOX_TOP), (800, BOX_BOTTOM), BLACK, 3)
    cv2.line(page, (230, 400), (740, 400), BLACK, 2)
    labels = [
        text_line("Date", x=110, y=310, width=80, height=22),
        text_line("DD / MM / YYYY", x=350, y=408, width=200, height=20),
    ]

    [slot] = detect_field_slots(page, labels)

    assert slot.label == "Date"
    assert slot.box.x == pytest.approx(230, abs=8)
    assert slot.box.right == pytest.approx(740, abs=8)
    assert slot.box.y > 332
    assert slot.box.bottom == pytest.approx(402, abs=4)


DATA_TABLE_HEADING_BOTTOM = 380
DATA_TABLE_ROW_HEIGHT = 80
DATA_TABLE_ROW_COUNT = 3
DATA_TABLE_COLUMNS = ((TABLE_LEFT, TABLE_SPLIT), (TABLE_SPLIT, TABLE_RIGHT))


def draw_data_table(page: np.ndarray) -> None:
    for column_left, column_right in DATA_TABLE_COLUMNS:
        heading_corners = ((column_left, BOX_TOP), (column_right, DATA_TABLE_HEADING_BOTTOM))
        cv2.rectangle(page, *heading_corners, BLACK, 3)
        for row in range(DATA_TABLE_ROW_COUNT):
            top = DATA_TABLE_HEADING_BOTTOM + row * DATA_TABLE_ROW_HEIGHT
            cv2.rectangle(
                page, (column_left, top), (column_right, top + DATA_TABLE_ROW_HEIGHT), BLACK, 3
            )


def test_each_empty_row_under_a_table_heading_is_a_field_named_by_the_heading() -> None:
    page = blank_page()
    draw_data_table(page)
    cv2.rectangle(page, (TABLE_LEFT, 700), (TABLE_SPLIT, 780), BLACK, 3)
    headings = [
        text_line("Country", x=120, y=320, width=150, height=25),
        text_line("TIN", x=620, y=320, width=60, height=25),
    ]

    slots = detect_field_slots(page, headings)

    assert len(slots) == DATA_TABLE_ROW_COUNT * len(DATA_TABLE_COLUMNS)
    assert [slot.label_box for slot in slots[:2]] == [heading.box for heading in headings]
    assert all(slot.box.y > DATA_TABLE_HEADING_BOTTOM for slot in slots)
    assert all(slot.box.bottom < 700 for slot in slots)


def test_detector_reads_each_table_heading_once() -> None:
    page = blank_page()
    draw_data_table(page)
    cv2.putText(page, "Country", (120, 350), cv2.FONT_HERSHEY_SIMPLEX, 1, BLACK, 2)
    cv2.putText(page, "TIN", (620, 350), cv2.FONT_HERSHEY_SIMPLEX, 1, BLACK, 2)
    label_reader = make_label_reader("Heading")

    slots = OpenCvFieldDetector(label_reader=label_reader).detect_fields(page)

    assert len(slots) == DATA_TABLE_ROW_COUNT * len(DATA_TABLE_COLUMNS)
    assert label_reader.call_count == len(DATA_TABLE_COLUMNS)


@pytest.mark.parametrize(
    ("cell_bottom", "labels"),
    [
        pytest.param(
            400,
            [text_line("The eMPF Platform", x=120, y=335, width=250, height=25)],
            id="text centred in its cell",
        ),
        pytest.param(
            600,
            [
                text_line("1. Hotline", x=120, y=310, width=250, height=25),
                text_line("2. Email", x=120, y=360, width=250, height=25),
                text_line("3. Fax", x=120, y=410, width=250, height=25),
            ],
            id="spaced-out list in one cell",
        ),
        pytest.param(
            370,
            [
                text_line("Monday to Friday", x=120, y=320, width=250, height=25),
                text_line("9:00 am - 6:00 pm", x=600, y=320, width=250, height=25),
                text_line("Closed", x=900, y=320, width=100, height=25),
            ],
            id="row of a printed timetable",
        ),
    ],
)
def test_printed_table_cells_are_not_fields(cell_bottom: int, labels: list[TextLine]) -> None:
    page = blank_page()
    cv2.rectangle(page, (TABLE_LEFT, BOX_TOP), (TABLE_RIGHT, cell_bottom), BLACK, 3)

    assert detect_field_slots(page, labels) == []


CHARACTER_BOX_WIDTH = 40
CHARACTER_BOX_TOP = 300
CHARACTER_BOX_BOTTOM = 360


def draw_character_boxes(page: np.ndarray, *, left: int, count: int) -> None:
    for index in range(count):
        box_left = left + index * CHARACTER_BOX_WIDTH
        corners = (
            (box_left, CHARACTER_BOX_TOP),
            (box_left + CHARACTER_BOX_WIDTH, CHARACTER_BOX_BOTTOM),
        )
        cv2.rectangle(page, *corners, BLACK, 2)


def test_run_of_empty_character_boxes_is_one_answer_until_a_printed_box() -> None:
    page = blank_page()
    cv2.rectangle(
        page, (TABLE_LEFT, CHARACTER_BOX_TOP), (TABLE_RIGHT, CHARACTER_BOX_BOTTOM), BLACK, 2
    )
    cv2.line(page, (380, CHARACTER_BOX_TOP), (380, CHARACTER_BOX_BOTTOM), BLACK, 2)
    draw_character_boxes(page, left=400, count=5)
    percent_box_left = 400 + 3 * CHARACTER_BOX_WIDTH
    cv2.line(page, (percent_box_left + 12, 345), (percent_box_left + 28, 315), BLACK, 2)
    labels = [
        text_line("Fund", x=120, y=315, width=100, height=25),
        text_line("Internal use", x=900, y=315, width=200, height=25),
    ]

    [slot] = detect_field_slots(page, labels)

    assert slot.box.x == pytest.approx(400, abs=4)
    assert slot.box.right < percent_box_left
    assert slot.label_box == labels[0].box


def test_second_write_on_line_after_a_label_is_its_own_answer() -> None:
    page = blank_page()
    cv2.line(page, (400, 400), (520, 400), BLACK, 2)
    cv2.line(page, (600, 400), (1000, 400), BLACK, 2)
    label = text_line("Mobile Phone No.", x=100, y=372, width=250, height=25)

    slots = detect_field_slots(page, [label])

    assert [slot.box.x for slot in slots] == [pytest.approx(400, abs=2), pytest.approx(600, abs=2)]
    assert slots[1].box.right == pytest.approx(1000, abs=2)
    assert slots[1].label_box == label.box


def test_line_printed_under_its_question_is_an_answer_named_by_the_question() -> None:
    page = blank_page()
    cv2.line(page, (100, 400), (1300, 400), BLACK, 2)
    question = text_line("Name of My Elected Scheme", x=100, y=300, width=400, height=25)

    [slot] = detect_field_slots(page, [question])

    assert slot.box.x == pytest.approx(100, abs=2)
    assert slot.box.bottom == pytest.approx(402, abs=2)
    assert slot.label_box == question.box


def test_underlined_heading_is_not_an_answer() -> None:
    page = blank_page()
    cv2.line(page, (100, 400), (600, 400), BLACK, 2)
    heading = text_line("Reminders Before Consolidating", x=100, y=370, width=440, height=28)

    assert detect_field_slots(page, [heading]) == []


def test_line_just_under_a_black_bar_is_not_an_answer() -> None:
    page = blank_page()
    cv2.rectangle(page, (800, 358), (1300, 388), BLACK, cv2.FILLED)
    cv2.line(page, (800, 400), (1300, 400), BLACK, 2)

    assert detect_field_slots(page, []) == []


def test_answer_starts_below_a_caption_printed_in_its_upper_part() -> None:
    page = blank_page()
    cv2.line(page, (450, 440), (1000, 440), BLACK, 2)
    labels = [
        text_line("Daytime Phone No.", x=100, y=393, width=300, height=47),
        text_line("(Country / Area Code)", x=450, y=362, width=300, height=20),
    ]

    [slot] = detect_field_slots(page, labels)

    assert slot.box.y >= 382
    assert slot.box.bottom == pytest.approx(442, abs=2)
