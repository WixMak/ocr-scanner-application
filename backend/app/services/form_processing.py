import numpy as np

from app.errors import MissingFormPagesError
from app.imaging.alignment import AlignmentResult, align_to_reference
from app.imaging.ink import erase_printed_ink, find_printed_ink, has_added_ink
from app.imaging.page import crop_box, encode_jpeg_data_url, normalise_page_width
from app.ocr.types import FieldValueReader
from app.schemas import (
    EngineReading,
    ExtractedField,
    ExtractionResult,
    FieldStatus,
    FieldType,
    PageSize,
    ResultPage,
    Template,
    TemplateDraft,
    TemplateField,
)
from app.services.field_detection import BlankFormFieldDetector, refine_detected_slots
from app.services.field_suggestions import suggest_template_fields
from app.services.page_pairing import PagePair, pair_scanned_pages
from app.services.template_store import TemplateStore

# Extra pixels around each field so small alignment errors don't clip handwriting.
FIELD_CROP_MARGIN_PX = 8
CHOSEN_OPTIONS_SEPARATOR = ", "


def build_template_draft(
    page_images: list[np.ndarray], *, detector: BlankFormFieldDetector, store: TemplateStore
) -> TemplateDraft:
    normalised_pages = [normalise_page_width(image) for image in page_images]
    return TemplateDraft(
        draft_id=store.save_draft_images(normalised_pages),
        pages=[_measure_page(page) for page in normalised_pages],
        fields=detect_template_fields(normalised_pages, detector=detector),
    )


def detect_template_fields(
    normalised_pages: list[np.ndarray], *, detector: BlankFormFieldDetector
) -> list[TemplateField]:
    slots_by_page = [
        refine_detected_slots(page, detector.detect_fields(page)) for page in normalised_pages
    ]
    return suggest_template_fields(slots_by_page)


def extract_form_values(
    page_images: list[np.ndarray],
    *,
    template: Template,
    blank_pages: list[np.ndarray],
    reader: FieldValueReader,
) -> ExtractionResult:
    scanned_pages = [normalise_page_width(page_image) for page_image in page_images]
    page_pairs = pair_scanned_pages(scanned_pages, blank_pages)
    _ensure_form_pages_were_scanned(template, page_pairs)
    alignments = {
        pair.template_page_index: align_to_reference(
            scanned_pages[pair.scan_page_index], blank_pages[pair.template_page_index]
        )
        for pair in page_pairs
    }
    printed_ink_by_page = {
        page_index: find_printed_ink(blank_pages[page_index])
        for page_index in {field.page_index for field in template.fields}
    }
    fields = [
        _extract_field(
            field,
            filled_form=alignments[field.page_index].image,
            blank_form=blank_pages[field.page_index],
            printed_ink=printed_ink_by_page[field.page_index],
            reader=reader,
        )
        for field in template.fields
    ]
    return ExtractionResult(
        template_id=template.id,
        template_name=template.name,
        pages=[
            _to_result_page(pair, alignment=alignments[pair.template_page_index], template=template)
            for pair in page_pairs
        ],
        values={field.key: field.value for field in fields},
        fields=fields,
    )


def _ensure_form_pages_were_scanned(template: Template, page_pairs: list[PagePair]) -> None:
    """Pages without fields, such as terms and conditions, may be left out of the scan."""
    scanned_template_pages = {pair.template_page_index for pair in page_pairs}
    pages_with_fields = {field.page_index for field in template.fields}
    missing_pages = sorted(pages_with_fields - scanned_template_pages)
    if missing_pages:
        raise MissingFormPagesError([page_index + 1 for page_index in missing_pages])
    if not page_pairs:
        raise MissingFormPagesError(list(range(1, len(template.pages) + 1)))


def _to_result_page(
    pair: PagePair, *, alignment: AlignmentResult, template: Template
) -> ResultPage:
    page_size = template.pages[pair.template_page_index]
    return ResultPage(
        page_index=pair.template_page_index,
        scan_page_number=pair.scan_page_index + 1,
        image_data_url=encode_jpeg_data_url(alignment.image),
        image_width=page_size.image_width,
        image_height=page_size.image_height,
        is_aligned=alignment.is_aligned,
    )


def _measure_page(page: np.ndarray) -> PageSize:
    image_height, image_width = page.shape[:2]
    return PageSize(image_width=image_width, image_height=image_height)


def _extract_field(
    field: TemplateField,
    *,
    filled_form: np.ndarray,
    blank_form: np.ndarray,
    printed_ink: np.ndarray,
    reader: FieldValueReader,
) -> ExtractedField:
    common = {
        "field_id": field.id,
        "key": field.key,
        "label": field.label,
        "field_type": field.field_type,
        "page_index": field.page_index,
        "box": field.box,
    }
    if field.field_type is FieldType.CHOICE:
        chosen_labels = _find_ticked_option_labels(
            field, filled_form=filled_form, blank_form=blank_form
        )
        return ExtractedField(
            **common,
            value=CHOSEN_OPTIONS_SEPARATOR.join(chosen_labels),
            confidence=1.0,
            status=_choice_status(chosen_count=len(chosen_labels)),
            readings=[],
        )
    filled_crop = crop_box(filled_form, field.box, margin=FIELD_CROP_MARGIN_PX)
    blank_crop = crop_box(blank_form, field.box, margin=FIELD_CROP_MARGIN_PX)
    if not has_added_ink(filled_crop, blank_crop):
        return ExtractedField(
            **common, value="", confidence=1.0, status=FieldStatus.EMPTY, readings=[]
        )
    printed_ink_crop = crop_box(printed_ink, field.box, margin=FIELD_CROP_MARGIN_PX)
    reading = reader.read_field(erase_printed_ink(filled_crop, printed_ink_crop), field.field_type)
    return ExtractedField(
        **common,
        value=reading.value,
        confidence=round(reading.confidence, 4),
        status=reading.status,
        readings=[
            EngineReading(
                engine=engine_reading.engine,
                text=engine_reading.text,
                confidence=round(engine_reading.confidence, 4),
            )
            for engine_reading in reading.readings
        ],
    )


def _find_ticked_option_labels(
    field: TemplateField, *, filled_form: np.ndarray, blank_form: np.ndarray
) -> list[str]:
    return [
        option.label
        for option in field.options
        if has_added_ink(
            crop_box(filled_form, option.box, margin=FIELD_CROP_MARGIN_PX),
            crop_box(blank_form, option.box, margin=FIELD_CROP_MARGIN_PX),
        )
    ]


def _choice_status(*, chosen_count: int) -> FieldStatus:
    """More than one tick usually means a correction or a mistake, so a person should check it."""
    if chosen_count == 0:
        return FieldStatus.EMPTY
    if chosen_count == 1:
        return FieldStatus.CONFIRMED
    return FieldStatus.REVIEW
