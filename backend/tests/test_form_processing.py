import cv2
import numpy as np
import pytest

from app.errors import MissingFormPagesError
from app.imaging.page import enclosing_box
from app.schemas import (
    BoundingBox,
    ChoiceOption,
    FieldStatus,
    FieldType,
    PageSize,
    Template,
    TemplateCreate,
    TemplateField,
)
from app.services.evaluation import (
    EngineScore,
    intersection_over_union,
    levenshtein_distance,
    record_page,
    score_detection,
)
from app.services.field_detection import DetectedSlot
from app.services.form_processing import build_template_draft, extract_form_values
from app.services.template_store import TemplateStore
from tests.conftest import FakeFieldDetector, FakeFieldReader, add_page_marks, write_on_form

UNWRITTEN_END_WIDTH_PX = 200
WHITE_LEVEL = 255


def create_name_template(
    store: TemplateStore, blank_form: np.ndarray, name_slot: DetectedSlot
) -> Template:
    draft = build_template_draft([blank_form], detector=FakeFieldDetector([name_slot]), store=store)
    return store.create(TemplateCreate(name="Form", draft_id=draft.draft_id, fields=draft.fields))


def test_draft_contains_detected_fields_and_saved_image(
    template_store: TemplateStore, blank_form: np.ndarray, name_slot: DetectedSlot
) -> None:
    draft = build_template_draft(
        [blank_form], detector=FakeFieldDetector([name_slot]), store=template_store
    )

    assert [field.key for field in draft.fields] == ["name"]
    assert draft.pages == [
        PageSize(image_width=blank_form.shape[1], image_height=blank_form.shape[0])
    ]
    assert template_store.draft_image_path(draft.draft_id, 0).exists()


def test_extracts_written_field_and_returns_values_json(
    template_store: TemplateStore,
    blank_form: np.ndarray,
    name_slot: DetectedSlot,
    fake_field_reader: FakeFieldReader,
) -> None:
    template = create_name_template(template_store, blank_form, name_slot)

    result = extract_form_values(
        [write_on_form(blank_form, "Chan")],
        template=template,
        blank_pages=template_store.load_blank_pages(template),
        reader=fake_field_reader,
    )

    assert result.pages[0].is_aligned
    assert result.values == {"name": "Chan Tai Man"}
    assert result.fields[0].status is FieldStatus.CONFIRMED
    assert result.fields[0].readings[0].engine == "fake"
    assert fake_field_reader.field_types == [FieldType.TEXT]
    assert result.pages[0].image_data_url.startswith("data:image/jpeg;base64,")


def test_reader_gets_the_field_without_its_printed_underline(
    template_store: TemplateStore,
    blank_form: np.ndarray,
    name_slot: DetectedSlot,
    fake_field_reader: FakeFieldReader,
) -> None:
    template = create_name_template(template_store, blank_form, name_slot)

    extract_form_values(
        [write_on_form(blank_form, "Chan")],
        template=template,
        blank_pages=template_store.load_blank_pages(template),
        reader=fake_field_reader,
    )

    [crop] = fake_field_reader.crops
    past_the_handwriting = crop[:, -UNWRITTEN_END_WIDTH_PX:]
    assert (past_the_handwriting == WHITE_LEVEL).all()


def test_blank_field_is_empty_and_skips_ocr(
    template_store: TemplateStore,
    blank_form: np.ndarray,
    name_slot: DetectedSlot,
    fake_field_reader: FakeFieldReader,
) -> None:
    template = create_name_template(template_store, blank_form, name_slot)

    result = extract_form_values(
        [blank_form.copy()],
        template=template,
        blank_pages=template_store.load_blank_pages(template),
        reader=fake_field_reader,
    )

    assert result.values == {"name": ""}
    assert result.fields[0].status is FieldStatus.EMPTY
    assert fake_field_reader.field_types == []


def create_two_page_name_template(
    store: TemplateStore, blank_form: np.ndarray, name_slot: DetectedSlot
) -> Template:
    draft = build_template_draft(
        [blank_form, blank_form], detector=FakeFieldDetector([name_slot]), store=store
    )
    return store.create(TemplateCreate(name="Form", draft_id=draft.draft_id, fields=draft.fields))


def test_draft_detects_fields_on_every_page(
    template_store: TemplateStore, blank_form: np.ndarray, name_slot: DetectedSlot
) -> None:
    draft = build_template_draft(
        [blank_form, blank_form],
        detector=FakeFieldDetector([name_slot]),
        store=template_store,
    )

    assert [(field.key, field.page_index) for field in draft.fields] == [
        ("name", 0),
        ("name_2", 1),
    ]
    assert len(draft.pages) == 2
    assert template_store.draft_image_path(draft.draft_id, 1).exists()


def test_reads_each_field_from_its_own_page(
    template_store: TemplateStore,
    blank_form: np.ndarray,
    name_slot: DetectedSlot,
    fake_field_reader: FakeFieldReader,
) -> None:
    template = create_two_page_name_template(template_store, blank_form, name_slot)

    result = extract_form_values(
        [blank_form.copy(), write_on_form(blank_form, "Chan")],
        template=template,
        blank_pages=template_store.load_blank_pages(template),
        reader=fake_field_reader,
    )

    assert result.values == {"name": "", "name_2": "Chan Tai Man"}
    assert [field.page_index for field in result.fields] == [0, 1]
    assert len(result.pages) == 2
    assert all(page.is_aligned for page in result.pages)


def create_marked_two_page_template(
    store: TemplateStore,
    blank_form: np.ndarray,
    name_slot: DetectedSlot,
    *,
    has_fields_on_second_page: bool,
) -> Template:
    pages = [add_page_marks(blank_form, 1), add_page_marks(blank_form, 2)]
    draft = build_template_draft(pages, detector=FakeFieldDetector([name_slot]), store=store)
    fields = [field for field in draft.fields if has_fields_on_second_page or field.page_index == 0]
    return store.create(TemplateCreate(name="Form", draft_id=draft.draft_id, fields=fields))


def test_reads_pages_scanned_in_a_different_order(
    template_store: TemplateStore,
    blank_form: np.ndarray,
    name_slot: DetectedSlot,
    fake_field_reader: FakeFieldReader,
) -> None:
    template = create_marked_two_page_template(
        template_store, blank_form, name_slot, has_fields_on_second_page=True
    )
    first_page, second_page = template_store.load_blank_pages(template)

    result = extract_form_values(
        [write_on_form(second_page, "Chan"), first_page.copy()],
        template=template,
        blank_pages=[first_page, second_page],
        reader=fake_field_reader,
    )

    assert result.values == {"name": "", "name_2": "Chan Tai Man"}
    assert [(page.page_index, page.scan_page_number) for page in result.pages] == [(0, 2), (1, 1)]


def test_pages_without_fields_may_be_left_out_of_the_scan(
    template_store: TemplateStore,
    blank_form: np.ndarray,
    name_slot: DetectedSlot,
    fake_field_reader: FakeFieldReader,
) -> None:
    template = create_marked_two_page_template(
        template_store, blank_form, name_slot, has_fields_on_second_page=False
    )
    blank_pages = template_store.load_blank_pages(template)

    result = extract_form_values(
        [write_on_form(blank_pages[0], "Chan")],
        template=template,
        blank_pages=blank_pages,
        reader=fake_field_reader,
    )

    assert result.values == {"name": "Chan Tai Man"}
    assert [(page.page_index, page.scan_page_number) for page in result.pages] == [(0, 1)]


def test_rejects_a_scan_missing_a_page_with_fields(
    template_store: TemplateStore,
    blank_form: np.ndarray,
    name_slot: DetectedSlot,
    fake_field_reader: FakeFieldReader,
) -> None:
    template = create_marked_two_page_template(
        template_store, blank_form, name_slot, has_fields_on_second_page=True
    )
    blank_pages = template_store.load_blank_pages(template)

    with pytest.raises(MissingFormPagesError, match="fields on them: 2") as raised:
        extract_form_values(
            [blank_pages[0].copy()],
            template=template,
            blank_pages=blank_pages,
            reader=fake_field_reader,
        )

    assert raised.value.page_numbers == [2]


def test_rejects_a_scan_with_no_page_of_a_template_without_fields(
    template_store: TemplateStore, blank_form: np.ndarray, fake_field_reader: FakeFieldReader
) -> None:
    draft = build_template_draft(
        [add_page_marks(blank_form, 1)], detector=FakeFieldDetector([]), store=template_store
    )
    template = template_store.create(
        TemplateCreate(name="Form", draft_id=draft.draft_id, fields=[])
    )

    with pytest.raises(MissingFormPagesError) as raised:
        extract_form_values(
            [add_page_marks(blank_form, 4)],
            template=template,
            blank_pages=template_store.load_blank_pages(template),
            reader=fake_field_reader,
        )

    assert raised.value.page_numbers == [1]


PERSONAL_BOX = BoundingBox(x=200, y=1100, width=40, height=40)
JOINT_BOX = BoundingBox(x=600, y=1100, width=40, height=40)
TICK_COLOUR = (120, 40, 20)
TICK_INSET_PX = 8


def create_account_type_template(store: TemplateStore, blank_form: np.ndarray) -> Template:
    account_type = TemplateField(
        id="account-type",
        key="account_type",
        label="Account Type",
        field_type=FieldType.CHOICE,
        page_index=0,
        box=enclosing_box([PERSONAL_BOX, JOINT_BOX]),
        options=[
            ChoiceOption(id="personal", label="Personal", box=PERSONAL_BOX),
            ChoiceOption(id="joint", label="Joint", box=JOINT_BOX),
        ],
    )
    draft_id = store.save_draft_images([blank_form])
    return store.create(TemplateCreate(name="Choices", draft_id=draft_id, fields=[account_type]))


def tick(page: np.ndarray, box: BoundingBox) -> None:
    cv2.line(
        page,
        (box.x + TICK_INSET_PX, box.y + TICK_INSET_PX),
        (box.right - TICK_INSET_PX, box.bottom - TICK_INSET_PX),
        TICK_COLOUR,
        4,
    )


@pytest.mark.parametrize(
    ("ticked_boxes", "expected_value", "expected_status"),
    [
        pytest.param([PERSONAL_BOX], "Personal", FieldStatus.CONFIRMED, id="one ticked"),
        pytest.param([], "", FieldStatus.EMPTY, id="none ticked"),
        pytest.param(
            [PERSONAL_BOX, JOINT_BOX], "Personal, Joint", FieldStatus.REVIEW, id="several ticked"
        ),
    ],
)
def test_choice_value_is_the_label_of_the_ticked_option(
    template_store: TemplateStore,
    blank_form: np.ndarray,
    fake_field_reader: FakeFieldReader,
    ticked_boxes: list[BoundingBox],
    expected_value: str,
    expected_status: FieldStatus,
) -> None:
    template = create_account_type_template(template_store, blank_form)
    filled_form = blank_form.copy()
    for box in ticked_boxes:
        tick(filled_form, box)

    result = extract_form_values(
        [filled_form],
        template=template,
        blank_pages=template_store.load_blank_pages(template),
        reader=fake_field_reader,
    )

    assert result.values == {"account_type": expected_value}
    assert result.fields[0].status is expected_status
    assert fake_field_reader.field_types == []


def test_scores_exact_matches_character_errors_and_digit_fields(
    template_store: TemplateStore,
    blank_form: np.ndarray,
    name_slot: DetectedSlot,
) -> None:
    template = create_name_template(template_store, blank_form, name_slot)
    result = extract_form_values(
        [write_on_form(blank_form, "Chan")],
        template=template,
        blank_pages=template_store.load_blank_pages(template),
        reader=FakeFieldReader(value="Chan Tai Mun"),
    )
    score = EngineScore(engine="fake")

    record_page(
        score,
        sample="form01.jpg",
        fields=result.fields,
        expected_values={"name": "Chan Tai Man", "unknown": "ignored"},
        seconds=2.0,
    )

    assert score.exact_match_rate == 0.0
    assert score.character_error_rate == 1 / len("chantaiman")
    assert score.digit_exact_rate == 0.0
    assert score.seconds_per_page == 2.0
    assert score.mismatches[0].actual == "Chan Tai Mun"


def test_digit_fields_are_scored_separately(
    template_store: TemplateStore,
    blank_form: np.ndarray,
    name_slot: DetectedSlot,
) -> None:
    template = create_name_template(template_store, blank_form, name_slot)
    template.fields[0].field_type = FieldType.NUMBER
    result = extract_form_values(
        [write_on_form(blank_form, "9123")],
        template=template,
        blank_pages=template_store.load_blank_pages(template),
        reader=FakeFieldReader(value="9123 4567"),
    )
    score = EngineScore(engine="fake")

    record_page(
        score, sample="a", fields=result.fields, expected_values={"name": "91234567"}, seconds=1
    )

    assert score.exact_match_rate == 1.0
    assert score.digit_exact_rate == 1.0
    assert score.mismatches == []


def test_levenshtein_distance() -> None:
    assert levenshtein_distance("陈大文", "陈大文") == 0
    assert levenshtein_distance("100号", "700号") == 1
    assert levenshtein_distance("", "abc") == 3
    assert levenshtein_distance("kitten", "sitting") == 3


NAME_BOX = BoundingBox(x=300, y=200, width=800, height=60)
SIGNATURE_BOX = BoundingBox(x=100, y=900, width=800, height=300)
SIGNATURE_LABEL_STRIP = BoundingBox(x=100, y=860, width=800, height=40)
TICK_BOX_SIZE = 30
TICK_BOX_GAP = 200


def make_saved_field(
    key: str, box: BoundingBox, *, page_index: int = 0, option_count: int = 0
) -> TemplateField:
    options = [
        ChoiceOption(
            id=f"{key}-{index}",
            label=f"Option {index}",
            box=BoundingBox(
                x=box.x + index * TICK_BOX_GAP, y=box.y, width=TICK_BOX_SIZE, height=TICK_BOX_SIZE
            ),
        )
        for index in range(option_count)
    ]
    field_type = FieldType.CHOICE if options else FieldType.TEXT
    return TemplateField(
        id=key,
        key=key,
        label=key,
        field_type=field_type,
        page_index=page_index,
        box=box,
        options=options,
    )


def test_detection_score_counts_matched_missed_and_made_up_fields() -> None:
    saved_name = make_saved_field("name", NAME_BOX)
    saved_signature = make_saved_field("signature", SIGNATURE_BOX, page_index=1)
    found_name = make_saved_field("name", NAME_BOX.model_copy(update={"x": 310}))
    signature_on_wrong_page = make_saved_field("signature", SIGNATURE_BOX)

    score = score_detection(
        "Form",
        expected=[saved_name, saved_signature],
        detected=[found_name, signature_on_wrong_page],
    )

    assert [(match.expected, match.detected) for match in score.matches] == [
        (saved_name, found_name)
    ]
    assert score.missed == [saved_signature]
    assert score.made_up == [signature_on_wrong_page]
    assert (score.recall, score.precision) == (0.5, 0.5)


def test_strip_beside_a_big_box_does_not_count_as_finding_it() -> None:
    score = score_detection(
        "Form",
        expected=[make_saved_field("signature", SIGNATURE_BOX)],
        detected=[make_saved_field("signature", SIGNATURE_LABEL_STRIP)],
    )

    assert score.matches == []
    assert intersection_over_union(SIGNATURE_BOX, SIGNATURE_LABEL_STRIP) == 0.0


def test_each_saved_field_is_matched_once_by_its_closest_detected_field() -> None:
    saved_name = make_saved_field("name", NAME_BOX)
    close_match = make_saved_field("close", NAME_BOX.model_copy(update={"width": 790}))
    rough_match = make_saved_field("rough", NAME_BOX.model_copy(update={"width": 600}))

    score = score_detection("Form", expected=[saved_name], detected=[rough_match, close_match])

    assert [match.detected for match in score.matches] == [close_match]
    assert score.made_up == [rough_match]


def test_choice_found_with_a_different_number_of_options_is_the_wrong_kind() -> None:
    saved_title = make_saved_field("title", NAME_BOX, option_count=3)
    found_title = make_saved_field("title", NAME_BOX, option_count=2)
    saved_name = make_saved_field("name", SIGNATURE_BOX)

    score = score_detection(
        "Form", expected=[saved_title, saved_name], detected=[found_title, saved_name]
    )

    assert len(score.matches) == 2
    assert [match.expected for match in score.different_kind] == [saved_title]


def test_detection_score_of_a_template_without_fields_is_zero() -> None:
    score = score_detection("Empty", expected=[], detected=[])

    assert (score.expected_count, score.detected_count) == (0, 0)
    assert (score.recall, score.precision) == (0.0, 0.0)
