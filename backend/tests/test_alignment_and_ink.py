import cv2
import numpy as np

from app.imaging.alignment import (
    MIN_INLIER_MATCHES,
    align_to_reference,
    count_shared_features,
    find_page_features,
)
from app.imaging.ink import (
    count_written_ink,
    erase_printed_ink,
    find_printed_ink,
    has_added_ink,
)
from app.imaging.page import crop_box
from app.schemas import BoundingBox
from tests.conftest import NAME_LABEL_BOX, NAME_UNDERLINE_Y, write_on_form

NAME_SLOT = BoundingBox(x=330, y=170, width=860, height=75)
MAX_MEAN_PIXEL_DIFFERENCE = 12
LABEL_AND_ANSWER = BoundingBox(x=90, y=170, width=1120, height=90)
WHITE = 255
MISALIGNMENT = np.float32([[1, 0, 2], [0, 1, 3]])


def rotate_and_shift(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    transform = cv2.getRotationMatrix2D((width / 2, height / 2), 2.5, 0.93)
    transform[:, 2] += (25, -18)
    return cv2.warpAffine(image, transform, (width, height), borderValue=(255, 255, 255))


def test_aligns_rotated_scan_back_onto_blank_form(blank_form: np.ndarray) -> None:
    scan = rotate_and_shift(blank_form)

    result = align_to_reference(scan, blank_form)

    assert result.is_aligned
    difference = cv2.absdiff(result.image, blank_form)
    assert float(difference.mean()) < MAX_MEAN_PIXEL_DIFFERENCE


def test_falls_back_to_resize_when_scan_has_no_matching_features(
    blank_form: np.ndarray,
) -> None:
    featureless_scan = np.full((500, 400, 3), 255, dtype=np.uint8)

    result = align_to_reference(featureless_scan, blank_form)

    assert not result.is_aligned
    assert result.image.shape == blank_form.shape


def test_counts_printed_features_shared_with_the_same_page(blank_form: np.ndarray) -> None:
    shared = count_shared_features(
        find_page_features(rotate_and_shift(blank_form)), find_page_features(blank_form)
    )

    assert shared >= MIN_INLIER_MATCHES


def test_unrelated_pages_share_no_features(blank_form: np.ndarray) -> None:
    sparse_page = np.full_like(blank_form, 255)
    cv2.putText(sparse_page, "OK", (700, 600), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 4)

    shared = count_shared_features(find_page_features(sparse_page), find_page_features(blank_form))

    assert shared == 0


def test_detects_handwriting_added_to_a_blank_field(blank_form: np.ndarray) -> None:
    filled = write_on_form(blank_form, "Chan")

    assert has_added_ink(crop_box(filled, NAME_SLOT), crop_box(blank_form, NAME_SLOT))


def test_blank_field_with_underline_has_no_added_ink(blank_form: np.ndarray) -> None:
    blank_crop = crop_box(blank_form, NAME_SLOT)

    assert not has_added_ink(blank_crop.copy(), blank_crop)


def test_printed_underline_is_not_counted_as_writing(blank_form: np.ndarray) -> None:
    underline_strip = crop_box(
        blank_form, BoundingBox(x=330, y=NAME_UNDERLINE_Y - 30, width=860, height=40)
    )

    assert count_written_ink(underline_strip) == 0


def test_empty_crop_has_no_ink() -> None:
    empty = np.zeros((0, 0, 3), dtype=np.uint8)

    assert count_written_ink(empty) == 0
    assert not has_added_ink(empty, empty)


def shift_slightly(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    return cv2.warpAffine(image, MISALIGNMENT, (width, height), borderValue=(255, 255, 255))


def test_erasing_print_leaves_only_the_handwriting(blank_form: np.ndarray) -> None:
    printed_ink = crop_box(find_printed_ink(blank_form), LABEL_AND_ANSWER)
    filled = shift_slightly(write_on_form(blank_form, "Chan"))

    handwriting_only = erase_printed_ink(crop_box(filled, LABEL_AND_ANSWER), printed_ink)

    label_right = NAME_LABEL_BOX.right - LABEL_AND_ANSWER.x
    assert (handwriting_only[:, :label_right] == WHITE).all()
    assert count_written_ink(handwriting_only) > 0


def test_erasing_print_from_a_slightly_misaligned_blank_form_leaves_it_white(
    blank_form: np.ndarray,
) -> None:
    printed_ink = crop_box(find_printed_ink(blank_form), LABEL_AND_ANSWER)

    erased = erase_printed_ink(crop_box(shift_slightly(blank_form), LABEL_AND_ANSWER), printed_ink)

    assert (erased == WHITE).all()
