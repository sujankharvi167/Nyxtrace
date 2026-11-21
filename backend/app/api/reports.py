from fastapi import APIRouter
from app.schemas.common import APIResponse
from app.core.logging import logger

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("", response_model=APIResponse)
async def list_reports():
    """List investigation reports. Report generation is in Stage 5."""
    logger.info("Reports list requested")
    return APIResponse(
        success=True,
        message="No reports generated yet.",
        data={"reports": [], "total": 0},
    )
