from http import HTTPStatus
from io import BytesIO

import httpx
import numpy as np
import pymupdf
from fastapi import UploadFile
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_blank_form_field_detector,
    get_field_value_reader,
    get_ollama_client,
    read_upload,
)
from app.config import get_settings
from app.errors import OcrEngineUnavailableError
from app.imaging.page import PDF_RENDER_DPI
from app.main import create_app
from app.ocr.types import FieldReading
from app.schemas import FieldType
from app.services.field_detection import DetectedSlot
from tests.conftest import add_page_marks, encode_image, write_on_form


def upload_blank_form(client: TestClient, blank_form: np.ndarray) -> dict:
    response = client.post(
        "/api/templates/drafts",
        files={"file": ("blank.png", encode_image(blank_form), "image/png")},
    )
    assert response.status_code == HTTPStatus.OK
    return response.json()


def save_template(client: TestClient, draft: dict, name: str = "Enrolment") -> dict:
    response = client.post(
        "/api/templates",
        json={"name": name, "draftId": draft["draftId"], "fields": draft["fields"]},
    )
    assert response.status_code == HTTPStatus.CREATED
    return response.json()


def test_template_lifecycle(api_client: TestClient, blank_form: np.ndarray) -> None:
    draft = upload_blank_form(api_client, blank_form)
    assert draft["fields"][0]["key"] == "name"
    assert draft["fields"][0]["fieldType"] == "text"
    draft_image = api_client.get(f"/api/templates/drafts/{draft['draftId']}/pages/0/image")
    assert draft_image.headers["content-type"] == "image/png"

    template = save_template(api_client, draft)
    template_id = template["id"]
    assert api_client.get("/api/templates").json()[0]["fieldCount"] == 1
    assert api_client.get(f"/api/templates/{template_id}").json()["name"] == "Enrolment"
    assert (
        api_client.get(f"/api/templates/{template_id}/pages/0/image").status_code == HTTPStatus.OK
    )

    renamed = api_client.put(
        f"/api/templates/{template_id}", json={"name": "Renamed", "fields": template["fields"]}
    )
    assert renamed.json()["name"] == "Renamed"

    assert api_client.delete(f"/api/templates/{template_id}").status_code == HTTPStatus.NO_CONTENT
    missing = api_client.get(f"/api/templates/{template_id}")
    assert missing.status_code == HTTPStatus.NOT_FOUND
    assert missing.json()["code"] == "template_not_found"


def test_extraction_returns_values_and_preview(
    api_client: TestClient, blank_form: np.ndarray
) -> None:
    template = save_template(api_client, upload_blank_form(api_client, blank_form))

    response = api_client.post(
        "/api/extractions",
        data={"templateId": template["id"]},
        files={
            "file": (
                "filled.jpg",
                encode_image(write_on_form(blank_form, "Chan"), ".jpg"),
                "image/jpeg",
            )
        },
    )

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["values"] == {"name": "Chan Tai Man"}
    assert body["fields"][0]["status"] == "confirmed"
    assert body["fields"][0]["pageIndex"] == 0
    assert len(body["pages"]) == 1
    assert body["pages"][0]["isAligned"] is True
    assert body["pages"][0]["imageDataUrl"].startswith("data:image/jpeg;base64,")


POINTS_PER_INCH = 72


def make_pdf_of(pages: list[np.ndarray]) -> bytes:
    """Size each PDF page to its image, so rendering gives back the same layout."""
    document = pymupdf.open()
    points_per_pixel = POINTS_PER_INCH / PDF_RENDER_DPI
    for page_image in pages:
        height, width = page_image.shape[:2]
        page = document.new_page(width=width * points_per_pixel, height=height * points_per_pixel)
        page.insert_image(page.rect, stream=encode_image(page_image))
    return document.tobytes()


def test_multi_page_pdf_becomes_a_multi_page_template(
    api_client: TestClient, blank_form: np.ndarray
) -> None:
    response = api_client.post(
        "/api/templates/drafts",
        files={"file": ("blank.pdf", make_pdf_of([blank_form, blank_form]), "application/pdf")},
    )
    draft = response.json()
    template = save_template(api_client, draft)

    assert [field["pageIndex"] for field in draft["fields"]] == [0, 1]
    assert len(template["pages"]) == 2
    second_page = api_client.get(f"/api/templates/{template['id']}/pages/1/image")
    assert second_page.status_code == HTTPStatus.OK
    missing_page = api_client.get(f"/api/templates/{template['id']}/pages/2/image")
    assert missing_page.status_code == HTTPStatus.NOT_FOUND


def test_extraction_missing_a_form_page_names_the_page(
    api_client: TestClient, blank_form: np.ndarray
) -> None:
    pages = [add_page_marks(blank_form, 1), add_page_marks(blank_form, 2)]
    draft = api_client.post(
        "/api/templates/drafts",
        files={"file": ("blank.pdf", make_pdf_of(pages), "application/pdf")},
    ).json()
    template = save_template(api_client, draft)

    response = api_client.post(
        "/api/extractions",
        data={"templateId": template["id"]},
        files={"file": ("filled.png", encode_image(pages[1]), "image/png")},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["code"] == "missing_form_pages"
    assert response.json()["pageNumbers"] == [1]


def test_negative_page_index_is_rejected(api_client: TestClient, blank_form: np.ndarray) -> None:
    template = save_template(api_client, upload_blank_form(api_client, blank_form))

    response = api_client.get(f"/api/templates/{template['id']}/pages/-1/image")

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_extraction_with_unknown_template_is_not_found(
    api_client: TestClient, blank_form: np.ndarray
) -> None:
    response = api_client.post(
        "/api/extractions",
        data={"templateId": "f" * 32},
        files={"file": ("filled.png", encode_image(blank_form), "image/png")},
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {"code": "template_not_found", "message": "Template not found."}


def test_unreadable_upload_is_rejected(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/templates/drafts", files={"file": ("notes.txt", b"hello", "text/plain")}
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json() == {
        "code": "unsupported_file",
        "message": "The file is not a readable image or PDF.",
    }


def test_oversized_upload_is_rejected(api_client: TestClient) -> None:
    oversized = b"\x89PNG" + b"0" * get_settings().max_upload_bytes

    response = api_client.post(
        "/api/templates/drafts", files={"file": ("big.png", oversized, "image/png")}
    )

    assert response.status_code == HTTPStatus.REQUEST_ENTITY_TOO_LARGE
    assert response.json()["code"] == "file_too_large"


def test_field_outside_image_is_rejected(api_client: TestClient, blank_form: np.ndarray) -> None:
    draft = upload_blank_form(api_client, blank_form)
    draft["fields"][0]["box"]["x"] = blank_form.shape[1]

    response = api_client.post(
        "/api/templates",
        json={"name": "Bad", "draftId": draft["draftId"], "fields": draft["fields"]},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["code"] == "field_outside_image"


class UnavailableFieldReader:
    def read_field(self, crop: np.ndarray, field_type: FieldType) -> FieldReading:
        raise OcrEngineUnavailableError("qwen3-vl:4b")


def test_engine_failure_is_reported_as_service_unavailable(
    api_client: TestClient, blank_form: np.ndarray
) -> None:
    template = save_template(api_client, upload_blank_form(api_client, blank_form))
    api_client.app.dependency_overrides[get_field_value_reader] = UnavailableFieldReader
    response = api_client.post(
        "/api/extractions",
        data={"templateId": template["id"]},
        files={"file": ("filled.png", encode_image(write_on_form(blank_form, "Lee")), "image/png")},
    )

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json()["code"] == "ocr_engine_unavailable"


class UnavailableFieldDetector:
    def detect_fields(self, image: np.ndarray) -> list[DetectedSlot]:
        raise OcrEngineUnavailableError("qwen3-vl:4b")


def test_draft_reports_service_unavailable_when_field_detection_is_down(
    api_client: TestClient, blank_form: np.ndarray
) -> None:
    api_client.app.dependency_overrides[get_blank_form_field_detector] = UnavailableFieldDetector

    response = api_client.post(
        "/api/templates/drafts",
        files={"file": ("blank.png", encode_image(blank_form), "image/png")},
    )

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json()["code"] == "ocr_engine_unavailable"


def test_health_reports_unreachable_ollama(api_client: TestClient) -> None:
    body = api_client.get("/api/health").json()

    assert body["isOllamaReachable"] is False
    assert body["fastModel"] == {"model": "qwen3-vl:4b", "isAvailable": False}


def test_health_reports_installed_models() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, json={"models": [{"name": "qwen3-vl:4b"}]})
    )
    app = create_app()
    app.dependency_overrides[get_ollama_client] = lambda: httpx.Client(
        base_url="http://ollama.test", transport=transport
    )

    body = TestClient(app).get("/api/health").json()

    assert body["isOllamaReachable"] is True
    assert body["fastModel"]["isAvailable"] is True
    assert body["accurateModel"]["isAvailable"] is False


def test_read_upload_accepts_file_at_the_limit() -> None:
    upload = UploadFile(file=BytesIO(b"1234"), filename="exact.png")

    assert read_upload(upload, max_bytes=4) == b"1234"
