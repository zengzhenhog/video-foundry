from fastapi import FastAPI

from auto_image.shared.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version)

    # Future phases register project, asset, script, voice, and render routers here.
    @app.get("/api/health", tags=["system"])
    def health() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "status": "ok",
        }

    return app


app = create_app()
