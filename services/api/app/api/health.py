from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    service: str
    mode: str


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    """Return a minimal liveness response without revealing sensitive configuration."""

    settings = request.app.state.settings
    return HealthResponse(status="ok", service="medicall-api", mode=settings.effective_voice_mode)
