from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import extractions, health, templates
from app.config import get_settings
from app.errors import AppError
from app.schemas import ErrorResponse


def create_app() -> FastAPI:
    app = FastAPI(title="OCR Form Scanner")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
    )
    app.add_exception_handler(AppError, _handle_app_error)
    app.include_router(templates.router)
    app.include_router(extractions.router)
    app.include_router(health.router)
    return app


async def _handle_app_error(_request: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, AppError):
        raise error
    body = ErrorResponse(code=error.code, message=error.message, page_numbers=error.page_numbers)
    return JSONResponse(
        status_code=error.status, content=body.model_dump(by_alias=True, exclude_none=True)
    )


app = create_app()
