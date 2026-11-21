from fastapi import APIRouter
from app.schemas.analysis import PlatformStats
from app.schemas.common import APIResponse
from app.core.logging import logger

router = APIRouter(prefix="/analysis", tags=["Analysis"])


@router.get("/stats", response_model=PlatformStats)
async def get_platform_stats():
    """Return platform-level statistics."""
    logger.info("Platform stats requested")
    return PlatformStats(
        total_transactions_analyzed=None,
        suspicious_transactions_detected=None,
        accounts_flagged=None,
        active_investigations=0,
        last_analysis_at=None,
        platform_status="ready",
    )


@router.get("/status", response_model=APIResponse)
async def get_analysis_status():
    """Return current analysis pipeline status."""
    logger.info("Analysis status requested")
    return APIResponse(
        success=True,
        message="Analysis pipeline ready. Upload a dataset to begin.",
        data={"stage": "awaiting_upload", "ml_pipeline": "not_trained"},
    )
