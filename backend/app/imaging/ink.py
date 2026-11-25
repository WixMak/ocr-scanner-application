import cv2
import numpy as np

from app.imaging.page import WHITE_BGR, to_grayscale

ADAPTIVE_BLOCK_SIZE = 31
ADAPTIVE_OFFSET = 15
RULE_HORIZONTAL_FRACTION = 4
RULE_VERTICAL_FRACTION = 2
MIN_RULE_LENGTH_PX = 20
RULE_DILATION_PX = 5
# Added ink is measured against the field height squared (roughly one written character), so a
# short value like "1" in a wide box still counts. Blank fields measure ~0.001, one digit ~0.016.
MIN_ADDED_INK_PER_CHARACTER_AREA = 0.01
# Printed ink is widened by this much before it is erased, so a small misalignment between the
# scan and the blank form doesn't leave fragments of a label for OCR to read.
PRINTED_INK_MARGIN_PX = 4


def count_written_ink(image: np.ndarray) -> int:
    """Count ink pixels, ignoring the printed underlines and box borders of the form."""
    if image.size == 0:
        return 0
    ink_mask = _find_ink(image)
    return int(np.count_nonzero(cv2.bitwise_and(ink_mask, cv2.bitwise_not(_find_rules(ink_mask)))))


def find_printed_ink(blank_page: np.ndarray) -> np.ndarray:
    """Mask everything printed on the blank form, widened to cover a small misalignment."""
    margin_size = 2 * PRINTED_INK_MARGIN_PX + 1
    return cv2.dilate(_find_ink(blank_page), np.ones((margin_size, margin_size), np.uint8))


def erase_printed_ink(filled_crop: np.ndarray, printed_ink_crop: np.ndarray) -> np.ndarray:
    """Keep only what was written on the form, by whitening where the blank form has print."""
    handwriting_only = filled_crop.copy()
    handwriting_only[printed_ink_crop > 0] = WHITE_BGR
    return handwriting_only


def _find_ink(image: np.ndarray) -> np.ndarray:
    return cv2.adaptiveThreshold(
        to_grayscale(image),
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        ADAPTIVE_BLOCK_SIZE,
        ADAPTIVE_OFFSET,
    )


def _find_rules(ink_mask: np.ndarray) -> np.ndarray:
    height, width = ink_mask.shape[:2]
    horizontal_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (max(width // RULE_HORIZONTAL_FRACTION, MIN_RULE_LENGTH_PX), 1)
    )
    vertical_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (1, max(height // RULE_VERTICAL_FRACTION, MIN_RULE_LENGTH_PX))
    )
    rules = cv2.bitwise_or(
        cv2.morphologyEx(ink_mask, cv2.MORPH_OPEN, horizontal_kernel),
        cv2.morphologyEx(ink_mask, cv2.MORPH_OPEN, vertical_kernel),
    )
    return cv2.dilate(rules, np.ones((RULE_DILATION_PX, RULE_DILATION_PX), np.uint8))


def has_added_ink(filled_crop: np.ndarray, blank_crop: np.ndarray) -> bool:
    crop_height = filled_crop.shape[0]
    if crop_height == 0:
        return False
    added_ink = count_written_ink(filled_crop) - count_written_ink(blank_crop)
    return added_ink / (crop_height * crop_height) > MIN_ADDED_INK_PER_CHARACTER_AREA
