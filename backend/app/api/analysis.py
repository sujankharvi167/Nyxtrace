from fastapi import APIRouter, File, UploadFile
from app.schemas.analysis import PlatformStats
from app.schemas.common import APIResponse
from app.core.logging import logger
from app.services.dataset_processor import load_latest_dataset, process_uploads
from pathlib import Path

router = APIRouter(prefix="/analysis", tags=["Analysis"])
BACKEND_DIR = Path(__file__).resolve().parents[2]


@router.get("/stats", response_model=PlatformStats)
async def get_platform_stats():
    """Return platform-level statistics."""
    logger.info("Platform stats requested")
    dataset = load_latest_dataset(BACKEND_DIR)
    if dataset:
        return PlatformStats(
            total_transactions_analyzed=int(dataset["total_transactions"]),
            suspicious_transactions_detected=None,
            accounts_flagged=None,
            active_investigations=0,
            last_analysis_at=dataset["uploaded_at"],
            platform_status="ready",
        )
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
    dataset = load_latest_dataset(BACKEND_DIR)
    if dataset:
        return APIResponse(
            success=True,
            message="Dataset processed and ready for later stages.",
            data={
                "stage": "dataset_ready",
                "ml_pipeline": "not_trained",
                "batch_id": dataset["batch_id"],
                "total_transactions": dataset["total_transactions"],
            },
        )
    return APIResponse(
        success=True,
        message="Analysis pipeline ready. Upload a dataset to begin.",
        data={"stage": "awaiting_upload", "ml_pipeline": "not_trained"},
    )


@router.post("/upload")
async def upload_dataset(files: list[UploadFile] = File(...)):
    """Upload and preprocess Elliptic++ or custom CSV datasets."""
    logger.info("Dataset upload requested with %d file(s)", len(files))
    result = await process_uploads(BACKEND_DIR, files)
    return APIResponse(success=True, message=str(result["message"]), data=result)


@router.get("/dataset")
async def get_latest_dataset():
    """Return the latest locally stored processed dataset summary."""
    dataset = load_latest_dataset(BACKEND_DIR)
    if not dataset:
        return APIResponse(
            success=True,
            message="No dataset has been uploaded.",
            data=None,
        )
    return APIResponse(success=True, message="Latest processed dataset.", data=dataset)
