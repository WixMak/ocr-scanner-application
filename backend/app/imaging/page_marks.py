from dataclasses import dataclass

import cv2
import numpy as np

from app.imaging.page import to_grayscale

# The forms print a row of solid squares along the bottom: one square in each corner,
# and between them one square per page number (page 3 has three).
MARK_BAND_HEIGHT_RATIO = 0.12
MIN_MARK_SIZE_PX = 20
MAX_MARK_SIZE_PX = 60
MAX_MARK_ASPECT_RATIO = 1.6
MIN_MARK_FILL_RATIO = 0.85
CORNER_MARK_EDGE_RATIO = 0.15


@dataclass(frozen=True)
class _Mark:
    left: int
    right: int
    center_x: float
    center_y: float
    height: int


def read_page_number(page: np.ndarray) -> int | None:
    """Count the page-number squares between the two corner squares at the foot of the page."""
    marks = _find_solid_squares(page)
    if len(marks) < 2:
        return None
    left_corner = min(marks, key=lambda mark: mark.left)
    right_corner = max(marks, key=lambda mark: mark.right)
    page_width = page.shape[1]
    if not _are_corner_marks(left_corner, right_corner, page_width=page_width):
        return None
    number_marks = [
        mark
        for mark in marks
        if left_corner.right < mark.left
        and mark.right < right_corner.left
        and _is_in_row_of(mark, left_corner, right_corner)
    ]
    return len(number_marks) or None


def _find_solid_squares(page: np.ndarray) -> list[_Mark]:
    gray = to_grayscale(page)
    band_top = round(gray.shape[0] * (1 - MARK_BAND_HEIGHT_RATIO))
    _, ink = cv2.threshold(gray[band_top:], 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    _, _, stats, _ = cv2.connectedComponentsWithStats(ink)
    return [
        _Mark(
            left=int(x),
            right=int(x + width),
            center_x=x + width / 2,
            center_y=band_top + y + height / 2,
            height=int(height),
        )
        for x, y, width, height, area in stats[1:]
        if _is_solid_square(width=int(width), height=int(height), area=int(area))
    ]


def _is_solid_square(*, width: int, height: int, area: int) -> bool:
    is_mark_sized = all(MIN_MARK_SIZE_PX <= side <= MAX_MARK_SIZE_PX for side in (width, height))
    if not is_mark_sized:
        return False
    is_squarish = max(width, height) / min(width, height) <= MAX_MARK_ASPECT_RATIO
    return is_squarish and area / (width * height) >= MIN_MARK_FILL_RATIO


def _are_corner_marks(left_corner: _Mark, right_corner: _Mark, *, page_width: int) -> bool:
    edge_width = page_width * CORNER_MARK_EDGE_RATIO
    return left_corner.center_x < edge_width and right_corner.center_x > page_width - edge_width


def _is_in_row_of(mark: _Mark, left_corner: _Mark, right_corner: _Mark) -> bool:
    """Follow the line through both corners, so a slightly skewed scan still counts every mark."""
    progress = (mark.center_x - left_corner.center_x) / (
        right_corner.center_x - left_corner.center_x
    )
    row_y = left_corner.center_y + progress * (right_corner.center_y - left_corner.center_y)
    return abs(mark.center_y - row_y) <= left_corner.height / 2
