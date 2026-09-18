from fastapi import FastAPI
from pydantic import BaseModel

from app.core.config import get_settings


class HealthResponse(BaseModel):
    status: str


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title=settings.app_name)

    @application.get("/health", response_model=HealthResponse, tags=["health"])
    def health() -> HealthResponse:
        """Process liveness only; this does not check database connectivity."""
        return HealthResponse(status="ok")

    return application


app = create_app()
