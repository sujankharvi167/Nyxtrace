from fastapi import APIRouter
from app.schemas.common import HealthResponse
from app.core.config import settings

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="operational",
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        service=settings.APP_NAME,
    )
