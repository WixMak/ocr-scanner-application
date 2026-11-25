import base64

import cv2
import numpy as np
import pymupdf

from app.errors import UnsupportedFileError
from app.schemas import BoundingBox

# A4 width at 200 DPI: enough resolution for handwriting while keeping OCR fast.
NORMALISED_PAGE_WIDTH = 1654
PDF_RENDER_DPI = 200
PDF_SIGNATURE = b"%PDF"
PREVIEW_JPEG_QUALITY = 85
WHITE_BGR = (255, 255, 255)


def load_page_images(content: bytes) -> list[np.ndarray]:
    """Decode an uploaded image as one page, or every page of a PDF, into BGR arrays."""
    if content.startswith(PDF_SIGNATURE):
        return _render_pdf_pages(content)
    buffer = np.frombuffer(content, dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if image is None:
        raise UnsupportedFileError()
    return [image]


def _render_pdf_pages(content: bytes) -> list[np.ndarray]:
    try:
        document = pymupdf.open(stream=content, filetype="pdf")
    except (RuntimeError, ValueError) as error:
        raise UnsupportedFileError() from error
    with document:
        if document.page_count == 0:
            raise UnsupportedFileError("The PDF has no pages.")
        return [_render_pdf_page(page) for page in document]


def _render_pdf_page(page: pymupdf.Page) -> np.ndarray:
    pixmap = page.get_pixmap(dpi=PDF_RENDER_DPI, alpha=False)
    pixels = np.frombuffer(pixmap.samples, dtype=np.uint8)
    rgb = pixels.reshape(pixmap.height, pixmap.width, pixmap.n)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def normalise_page_width(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    if width == NORMALISED_PAGE_WIDTH:
        return image
    scale = NORMALISED_PAGE_WIDTH / width
    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    return cv2.resize(
        image, (NORMALISED_PAGE_WIDTH, round(height * scale)), interpolation=interpolation
    )


def crop_box(image: np.ndarray, box: BoundingBox, *, margin: int = 0) -> np.ndarray:
    image_height, image_width = image.shape[:2]
    left = max(box.x - margin, 0)
    top = max(box.y - margin, 0)
    right = min(box.right + margin, image_width)
    bottom = min(box.bottom + margin, image_height)
    return image[top:bottom, left:right]


def is_box_within(box: BoundingBox, *, width: int, height: int) -> bool:
    return box.right <= width and box.bottom <= height


def enclosing_box(boxes: list[BoundingBox]) -> BoundingBox:
    left = min(box.x for box in boxes)
    top = min(box.y for box in boxes)
    right = max(box.right for box in boxes)
    bottom = max(box.bottom for box in boxes)
    return BoundingBox(x=left, y=top, width=right - left, height=bottom - top)


def encode_png(image: np.ndarray) -> bytes:
    is_encoded, buffer = cv2.imencode(".png", image)
    if not is_encoded:
        raise ValueError("Could not encode image as PNG")
    return buffer.tobytes()


def encode_jpeg_data_url(image: np.ndarray) -> str:
    is_encoded, buffer = cv2.imencode(
        ".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, PREVIEW_JPEG_QUALITY]
    )
    if not is_encoded:
        raise ValueError("Could not encode image as JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(buffer.tobytes()).decode("ascii")


def to_grayscale(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
