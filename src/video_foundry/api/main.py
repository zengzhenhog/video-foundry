from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from video_foundry.api.routes.assets import router as assets_router
from video_foundry.api.routes.projects import router as projects_router
from video_foundry.api.routes.script import router as script_router
from video_foundry.api.routes.storyboard import router as storyboard_router
from video_foundry.api.routes.subtitles import router as subtitles_router
from video_foundry.api.routes.voice import global_router as voice_global_router
from video_foundry.api.routes.voice import project_router as voice_project_router
from video_foundry.shared.config import get_settings
from video_foundry.shared.errors import AppError, ErrorDetail, ErrorResponse


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
    app.include_router(assets_router)
    app.include_router(script_router)
    app.include_router(voice_global_router)
    app.include_router(voice_project_router)
    app.include_router(storyboard_router)
    app.include_router(subtitles_router)

    # Future phases register job and render routers here.
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

