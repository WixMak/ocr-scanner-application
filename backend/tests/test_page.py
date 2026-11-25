import base64

import numpy as np
import pymupdf
import pytest

from app.errors import UnsupportedFileError
from app.imaging.page import (
    NORMALISED_PAGE_WIDTH,
    crop_box,
    encode_jpeg_data_url,
    is_box_within,
    load_page_images,
    normalise_page_width,
    to_grayscale,
)
from app.schemas import BoundingBox
from tests.conftest import encode_image


def make_pdf(page_count: int) -> bytes:
    document = pymupdf.open()
    for _ in range(page_count):
        page = document.new_page()
        page.insert_text((72, 72), "Name:")
    return document.tobytes()


def test_loads_png_upload_as_one_bgr_page(blank_form: np.ndarray) -> None:
    pages = load_page_images(encode_image(blank_form))

    assert [page.shape for page in pages] == [blank_form.shape]


def test_renders_every_pdf_page() -> None:
    pages = load_page_images(make_pdf(page_count=2))

    assert len(pages) == 2
    for page in pages:
        assert page.ndim == 3
        assert page.shape[2] == 3
        assert page.shape[1] > page.shape[0] * 0.5


def test_rejects_pdf_without_pages() -> None:
    with pytest.raises(UnsupportedFileError):
        load_page_images(b"%PDF-1.7\n%%EOF")


def test_rejects_bytes_that_are_not_an_image() -> None:
    with pytest.raises(UnsupportedFileError):
        load_page_images(b"definitely not an image")


@pytest.mark.parametrize("source_width", [800, NORMALISED_PAGE_WIDTH, 3000])
def test_normalises_width_and_keeps_aspect_ratio(source_width: int) -> None:
    image = np.zeros((source_width * 2, source_width, 3), dtype=np.uint8)

    normalised = normalise_page_width(image)

    assert normalised.shape[1] == NORMALISED_PAGE_WIDTH
    assert normalised.shape[0] == NORMALISED_PAGE_WIDTH * 2


def test_crop_box_clips_margin_to_image_edges() -> None:
    image = np.zeros((100, 200, 3), dtype=np.uint8)

    crop = crop_box(image, BoundingBox(x=5, y=5, width=190, height=90), margin=20)

    assert crop.shape[:2] == (100, 200)


def test_is_box_within_checks_right_and_bottom_edges() -> None:
    assert is_box_within(BoundingBox(x=0, y=0, width=100, height=50), width=100, height=50)
    assert not is_box_within(BoundingBox(x=1, y=0, width=100, height=50), width=100, height=50)


def test_encodes_preview_as_jpeg_data_url(blank_form: np.ndarray) -> None:
    data_url = encode_jpeg_data_url(blank_form)

    prefix, encoded = data_url.split(",", 1)
    assert prefix == "data:image/jpeg;base64"
    assert base64.b64decode(encoded)[:2] == b"\xff\xd8"


def test_to_grayscale_passes_through_single_channel_images() -> None:
    gray = np.zeros((10, 10), dtype=np.uint8)

    assert to_grayscale(gray) is gray
