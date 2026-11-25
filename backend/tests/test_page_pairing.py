import cv2
import numpy as np

from app.imaging.page import NORMALISED_PAGE_WIDTH
from app.services.page_pairing import PagePair, pair_scanned_pages
from tests.conftest import BLACK, PAGE_HEIGHT, add_page_marks


def make_terms_page() -> np.ndarray:
    page = np.full((PAGE_HEIGHT, NORMALISED_PAGE_WIDTH, 3), 255, dtype=np.uint8)
    for row in range(8):
        cv2.putText(
            page,
            f"TERM {row + 1}: CONDITIONS APPLY {row * 13} WXYZ",
            (120, 150 + row * 110),
            cv2.FONT_HERSHEY_DUPLEX,
            1.3,
            BLACK,
            2,
        )
    return page


def make_white_page() -> np.ndarray:
    return np.full((PAGE_HEIGHT, NORMALISED_PAGE_WIDTH, 3), 255, dtype=np.uint8)


def pairs_of(*scan_to_template: tuple[int, int]) -> list[PagePair]:
    return [
        PagePair(scan_page_index=scan_index, template_page_index=template_index)
        for scan_index, template_index in scan_to_template
    ]


def test_pairs_reordered_pages_by_their_marks_and_allows_left_out_pages(
    blank_form: np.ndarray,
) -> None:
    blank_pages = [add_page_marks(blank_form, number) for number in (1, 2, 3)]
    scanned_pages = [blank_pages[2], blank_pages[0]]

    assert pair_scanned_pages(scanned_pages, blank_pages) == pairs_of((1, 0), (0, 2))


def test_skips_a_duplicate_page_instead_of_guessing_where_it_goes(blank_form: np.ndarray) -> None:
    blank_pages = [add_page_marks(blank_form, number) for number in (1, 2)]
    scanned_pages = [blank_pages[0], blank_pages[0]]

    assert pair_scanned_pages(scanned_pages, blank_pages) == pairs_of((0, 0))


def test_skips_a_marked_page_the_template_does_not_have(blank_form: np.ndarray) -> None:
    blank_pages = [add_page_marks(blank_form, 1)]
    scanned_pages = [add_page_marks(blank_form, 5), blank_pages[0]]

    assert pair_scanned_pages(scanned_pages, blank_pages) == pairs_of((1, 0))


def test_pairs_unmarked_pages_by_printed_content(blank_form: np.ndarray) -> None:
    blank_pages = [blank_form, make_terms_page()]
    scanned_pages = [make_terms_page(), blank_form.copy()]

    assert pair_scanned_pages(scanned_pages, blank_pages) == pairs_of((1, 0), (0, 1))


def test_falls_back_to_page_order_when_nothing_else_matches() -> None:
    blank_pages = [make_terms_page(), make_terms_page()]
    scanned_pages = [make_white_page(), make_white_page()]

    assert pair_scanned_pages(scanned_pages, blank_pages) == pairs_of((0, 0), (1, 1))


def test_leaves_out_an_unrecognised_page_when_page_counts_differ(blank_form: np.ndarray) -> None:
    blank_pages = [add_page_marks(blank_form, 1)]
    scanned_pages = [make_white_page(), blank_pages[0]]

    assert pair_scanned_pages(scanned_pages, blank_pages) == pairs_of((1, 0))


def test_pairs_an_unrecognised_page_with_the_free_page_in_its_position(
    blank_form: np.ndarray,
) -> None:
    blank_pages = [add_page_marks(blank_form, 1), add_page_marks(blank_form, 2)]
    scanned_pages = [blank_pages[0], make_white_page()]

    assert pair_scanned_pages(scanned_pages, blank_pages) == pairs_of((0, 0), (1, 1))


def test_position_fallback_never_reuses_a_paired_template_page(blank_form: np.ndarray) -> None:
    blank_pages = [add_page_marks(blank_form, 1), add_page_marks(blank_form, 2)]
    scanned_pages = [make_white_page(), blank_pages[0]]

    assert pair_scanned_pages(scanned_pages, blank_pages) == pairs_of((1, 0))
