from enum import StrEnum
from http import HTTPStatus


class ErrorCode(StrEnum):
    UNSUPPORTED_FILE = "unsupported_file"
    FILE_TOO_LARGE = "file_too_large"
    TEMPLATE_NOT_FOUND = "template_not_found"
    DRAFT_NOT_FOUND = "draft_not_found"
    FIELD_OUTSIDE_IMAGE = "field_outside_image"
    MISSING_FORM_PAGES = "missing_form_pages"
    OCR_ENGINE_UNAVAILABLE = "ocr_engine_unavailable"


class AppError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        status: HTTPStatus,
        message: str,
        *,
        page_numbers: list[int] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.message = message
        self.page_numbers = page_numbers


class UnsupportedFileError(AppError):
    def __init__(self, message: str = "The file is not a readable image or PDF.") -> None:
        super().__init__(ErrorCode.UNSUPPORTED_FILE, HTTPStatus.UNPROCESSABLE_ENTITY, message)


class FileTooLargeError(AppError):
    def __init__(self, max_bytes: int) -> None:
        super().__init__(
            ErrorCode.FILE_TOO_LARGE,
            HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            f"The file is larger than {max_bytes} bytes.",
        )


class TemplateNotFoundError(AppError):
    def __init__(self) -> None:
        super().__init__(ErrorCode.TEMPLATE_NOT_FOUND, HTTPStatus.NOT_FOUND, "Template not found.")


class DraftNotFoundError(AppError):
    def __init__(self) -> None:
        super().__init__(ErrorCode.DRAFT_NOT_FOUND, HTTPStatus.NOT_FOUND, "Draft not found.")


class FieldOutsideImageError(AppError):
    def __init__(self, field_key: str) -> None:
        super().__init__(
            ErrorCode.FIELD_OUTSIDE_IMAGE,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            f"Field '{field_key}' extends outside the form image.",
        )


class MissingFormPagesError(AppError):
    def __init__(self, page_numbers: list[int]) -> None:
        listed_pages = ", ".join(str(number) for number in page_numbers)
        super().__init__(
            ErrorCode.MISSING_FORM_PAGES,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            f"The scan is missing form pages with fields on them: {listed_pages}.",
            page_numbers=page_numbers,
        )


class OcrEngineUnavailableError(AppError):
    def __init__(self, engine_name: str) -> None:
        super().__init__(
            ErrorCode.OCR_ENGINE_UNAVAILABLE,
            HTTPStatus.SERVICE_UNAVAILABLE,
            f"OCR engine '{engine_name}' is unavailable. Is Ollama running?",
        )
