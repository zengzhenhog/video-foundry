from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from auto_image.api.routes.projects import router as projects_router
from auto_image.shared.config import get_settings
from auto_image.shared.errors import AppError, ErrorDetail, ErrorResponse


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version)

    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_response())

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        error = ErrorResponse(
            error=ErrorDetail(
                code="validation_error",
                message="Request validation failed.",
                step="request_validation",
                retryable=False,
                suggested_correction="Check the request payload and path parameters.",
                details={"errors": [_sanitize_validation_error(item) for item in exc.errors()]},
            )
        )
        return JSONResponse(status_code=422, content=error.model_dump(mode="json"))

    app.include_router(projects_router)

    # Future phases register asset, script, voice, storyboard, job, and render routers here.
    @app.get("/api/health", tags=["system"])
    def health() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "status": "ok",
        }

    return app


def _sanitize_validation_error(error: dict) -> dict:
    return {
        key: value
        for key, value in error.items()
        if key not in {"ctx", "input", "url"}
    }


app = create_app()
