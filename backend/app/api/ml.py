from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.schemas.common import APIResponse
from app.services.ml_engine import DEFAULT_THRESHOLD, ml_engine


router = APIRouter(prefix="/ml", tags=["Machine Learning"])


class TrainingRequest(BaseModel):
    classification_threshold: float = Field(
        default=DEFAULT_THRESHOLD,
        ge=0.05,
        le=0.95,
    )


@router.get("/readiness")
async def dataset_readiness():
    readiness = ml_engine.readiness()
    return APIResponse(
        success=True,
        message=str(readiness["message"]),
        data=readiness,
    )


@router.get("/status")
async def model_status():
    state = ml_engine.get_status()
    data = {
        **state,
        "model_available": ml_engine.model_path.is_file(),
        "predictions_available": ml_engine.predictions_path.is_file(),
    }
    return APIResponse(success=True, message=str(state.get("message", "Model status.")), data=data)


@router.get("/progress")
async def training_progress():
    state = ml_engine.get_status()
    return APIResponse(success=True, message=str(state.get("message", "Training progress.")), data=state)


@router.post("/train")
async def train_models(request: TrainingRequest = TrainingRequest()):
    state = ml_engine.start_training(request.classification_threshold)
    return APIResponse(
        success=True,
        message="Model comparison training started.",
        data=state,
    )


@router.get("/evaluation")
async def evaluation():
    return APIResponse(
        success=True,
        message="Held-out model evaluation results.",
        data=ml_engine.evaluation(),
    )


@router.get("/models")
async def model_comparison():
    return APIResponse(
        success=True,
        message="Model comparison results.",
        data=ml_engine.model_comparison(),
    )


async def _prediction_result(
    page: int,
    page_size: int,
    threshold: float,
    search: Optional[str],
    predicted_class: Optional[str],
    suspicious_only: bool,
):
    try:
        return await run_in_threadpool(
            ml_engine.predictions,
            page,
            page_size,
            threshold,
            search,
            predicted_class,
            suspicious_only,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not load predictions: {exc}") from exc


@router.get("/predictions")
async def predictions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    threshold: float = Query(default=DEFAULT_THRESHOLD, ge=0.0, le=1.0),
    search: Optional[str] = Query(default=None, max_length=128),
    predicted_class: Optional[str] = Query(default=None),
):
    data = await _prediction_result(page, page_size, threshold, search, predicted_class, False)
    return APIResponse(success=True, message="Paginated transaction predictions.", data=data)


@router.get("/suspicious")
async def suspicious_transactions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    threshold: float = Query(default=DEFAULT_THRESHOLD, ge=0.0, le=1.0),
    search: Optional[str] = Query(default=None, max_length=128),
):
    data = await _prediction_result(page, page_size, threshold, search, "illicit", True)
    return APIResponse(success=True, message="Paginated model-flagged transactions.", data=data)


@router.get("/feature-importance")
async def feature_importance(limit: int = Query(default=20, ge=1, le=30)):
    return APIResponse(
        success=True,
        message="Selected model global feature importance.",
        data=ml_engine.feature_importance(limit),
    )


@router.get("/transactions/{transaction_id}/explanation")
async def transaction_explanation(transaction_id: str):
    data = await run_in_threadpool(ml_engine.explain, transaction_id)
    return APIResponse(
        success=True,
        message="Local feature-ablation explanation.",
        data=data,
    )
