import cv2
import numpy as np
import pytest

from app.imaging.page_marks import read_page_number
from tests.conftest import (
    BLACK,
    FIRST_NUMBER_MARK_X,
    PAGE_MARK_SIZE_PX,
    PAGE_MARK_TOP_FROM_BOTTOM_PX,
    add_page_marks,
)

SKEW_DEGREES = 1.5
OFF_ROW_GAP_PX = 4
BAR_FROM_BOTTOM_PX = 40
BAR_HEIGHT_PX = 30


def skew(page: np.ndarray) -> np.ndarray:
    height, width = page.shape[:2]
    transform = cv2.getRotationMatrix2D((width / 2, height / 2), SKEW_DEGREES, 1.0)
    return cv2.warpAffine(page, transform, (width, height), borderValue=(255, 255, 255))


def draw_square(page: np.ndarray, *, left: int, filled: bool) -> None:
    top = page.shape[0] - PAGE_MARK_TOP_FROM_BOTTOM_PX
    thickness = -1 if filled else 3
    cv2.rectangle(
        page, (left, top), (left + PAGE_MARK_SIZE_PX, top + PAGE_MARK_SIZE_PX), BLACK, thickness
    )


@pytest.mark.parametrize("page_number", [1, 3, 9])
def test_counts_the_marks_between_the_corner_squares(
    blank_form: np.ndarray, page_number: int
) -> None:
    assert read_page_number(add_page_marks(blank_form, page_number)) == page_number


def test_reads_marks_on_a_slightly_skewed_scan(blank_form: np.ndarray) -> None:
    assert read_page_number(skew(add_page_marks(blank_form, 4))) == 4


def test_page_without_marks_has_no_number(blank_form: np.ndarray) -> None:
    assert read_page_number(blank_form) is None


def test_corner_squares_alone_give_no_number(blank_form: np.ndarray) -> None:
    corners_only = add_page_marks(blank_form, 0)

    assert read_page_number(corners_only) is None


def test_squares_away_from_the_corners_are_not_page_marks(blank_form: np.ndarray) -> None:
    page = blank_form.copy()
    for left in (600, 700, 800):
        draw_square(page, left=left, filled=True)

    assert read_page_number(page) is None


def test_empty_tick_boxes_in_the_row_are_not_counted(blank_form: np.ndarray) -> None:
    page = add_page_marks(blank_form, 2)
    draw_square(page, left=FIRST_NUMBER_MARK_X + 400, filled=False)

    assert read_page_number(page) == 2


def test_squares_off_the_row_are_not_counted(blank_form: np.ndarray) -> None:
    page = add_page_marks(blank_form, 2)
    off_row_top = page.shape[0] - PAGE_MARK_TOP_FROM_BOTTOM_PX - PAGE_MARK_SIZE_PX - OFF_ROW_GAP_PX
    cv2.rectangle(
        page,
        (900, off_row_top),
        (900 + PAGE_MARK_SIZE_PX, off_row_top + PAGE_MARK_SIZE_PX),
        BLACK,
        -1,
    )

    assert read_page_number(page) == 2


def test_a_black_bar_along_the_bottom_is_not_a_page_mark(blank_form: np.ndarray) -> None:
    page = add_page_marks(blank_form, 3)
    bar_top = page.shape[0] - BAR_FROM_BOTTOM_PX
    cv2.rectangle(page, (0, bar_top), (page.shape[1], bar_top + BAR_HEIGHT_PX), BLACK, -1)

    assert read_page_number(page) == 3
