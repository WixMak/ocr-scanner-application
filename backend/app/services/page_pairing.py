from dataclasses import dataclass
from itertools import product

import numpy as np

from app.imaging.alignment import MIN_INLIER_MATCHES, count_shared_features, find_page_features
from app.imaging.page_marks import read_page_number


@dataclass(frozen=True)
class PagePair:
    template_page_index: int
    scan_page_index: int


@dataclass(frozen=True)
class _ContentMatch:
    shared_feature_count: int
    scan_page_index: int
    template_page_index: int

    @property
    def preference(self) -> tuple[int, int, int]:
        """Most shared features first; on a tie, keep the scan's own page order."""
        return (
            -self.shared_feature_count,
            abs(self.scan_page_index - self.template_page_index),
            self.scan_page_index,
        )


def pair_scanned_pages(
    scanned_pages: list[np.ndarray], blank_pages: list[np.ndarray]
) -> list[PagePair]:
    """Find which template page each scanned page is, so pages can be left out or reordered.

    Pages are paired by their printed page marks. A scanned page whose marks can't be read
    is paired by matching printed content, and last by position when the scan has exactly
    as many pages as the template. Scanned pages that match no template page are left out.
    """
    scan_page_numbers = [read_page_number(page) for page in scanned_pages]
    pairs = _pair_by_page_marks(scan_page_numbers, blank_pages)
    pairs += _pair_by_printed_content(
        scanned_pages, blank_pages, unpaired=_find_unpaired(pairs, scan_page_numbers, blank_pages)
    )
    if len(scanned_pages) == len(blank_pages):
        pairs += _pair_by_position(_find_unpaired(pairs, scan_page_numbers, blank_pages))
    return sorted(pairs, key=lambda pair: pair.template_page_index)


@dataclass(frozen=True)
class _UnpairedPages:
    unmarked_scan_page_indexes: list[int]
    template_page_indexes: list[int]


def _find_unpaired(
    pairs: list[PagePair], scan_page_numbers: list[int | None], blank_pages: list[np.ndarray]
) -> _UnpairedPages:
    """Scanned pages with readable marks never fall back: a duplicate page must not be guessed."""
    paired_scans = {pair.scan_page_index for pair in pairs}
    paired_templates = {pair.template_page_index for pair in pairs}
    return _UnpairedPages(
        unmarked_scan_page_indexes=[
            index
            for index, page_number in enumerate(scan_page_numbers)
            if page_number is None and index not in paired_scans
        ],
        template_page_indexes=[
            index for index in range(len(blank_pages)) if index not in paired_templates
        ],
    )


def _pair_by_page_marks(
    scan_page_numbers: list[int | None], blank_pages: list[np.ndarray]
) -> list[PagePair]:
    template_index_by_number: dict[int, int] = {}
    for template_index, blank_page in enumerate(blank_pages):
        page_number = read_page_number(blank_page)
        if page_number is not None:
            template_index_by_number.setdefault(page_number, template_index)

    pairs: list[PagePair] = []
    for scan_index, page_number in enumerate(scan_page_numbers):
        if page_number is None or page_number not in template_index_by_number:
            continue
        template_index = template_index_by_number.pop(page_number)
        pairs.append(PagePair(template_page_index=template_index, scan_page_index=scan_index))
    return pairs


def _pair_by_printed_content(
    scanned_pages: list[np.ndarray], blank_pages: list[np.ndarray], *, unpaired: _UnpairedPages
) -> list[PagePair]:
    if not unpaired.unmarked_scan_page_indexes or not unpaired.template_page_indexes:
        return []
    scan_features = {
        index: find_page_features(scanned_pages[index])
        for index in unpaired.unmarked_scan_page_indexes
    }
    template_features = {
        index: find_page_features(blank_pages[index]) for index in unpaired.template_page_indexes
    }
    matches = [
        _ContentMatch(
            shared_feature_count=count_shared_features(
                scan_features[scan_index], template_features[template_index]
            ),
            scan_page_index=scan_index,
            template_page_index=template_index,
        )
        for scan_index, template_index in product(scan_features, template_features)
    ]
    confident_matches = [
        match for match in matches if match.shared_feature_count >= MIN_INLIER_MATCHES
    ]
    return _take_best_matches(confident_matches)


def _take_best_matches(matches: list[_ContentMatch]) -> list[PagePair]:
    pairs: list[PagePair] = []
    paired_scans: set[int] = set()
    paired_templates: set[int] = set()
    for match in sorted(matches, key=lambda match: match.preference):
        if match.scan_page_index in paired_scans or match.template_page_index in paired_templates:
            continue
        paired_scans.add(match.scan_page_index)
        paired_templates.add(match.template_page_index)
        pairs.append(
            PagePair(
                template_page_index=match.template_page_index,
                scan_page_index=match.scan_page_index,
            )
        )
    return pairs


def _pair_by_position(unpaired: _UnpairedPages) -> list[PagePair]:
    free_template_indexes = set(unpaired.template_page_indexes)
    return [
        PagePair(template_page_index=scan_index, scan_page_index=scan_index)
        for scan_index in unpaired.unmarked_scan_page_indexes
        if scan_index in free_template_indexes
    ]
