from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.schemas.common import APIResponse
from app.services.risk_engine import risk_engine


router = APIRouter(prefix="/risk", tags=["Risk Intelligence"])


class TransactionAssessmentRequest(BaseModel):
    transaction_ids: list[str] = Field(min_length=1, max_length=500)


class CaseCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    priority: Literal["critical", "high", "medium", "low"] = "medium"
    status: Literal["open", "under_review", "escalated", "resolved", "closed"] = "open"
    primary_transaction_id: Optional[str] = Field(default=None, max_length=128)
    transaction_ids: list[str] = Field(default_factory=list, max_length=500)
    risk_assessment_reference: Optional[str] = Field(default=None, max_length=128)


class CaseUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=5000)
    priority: Optional[Literal["critical", "high", "medium", "low"]] = None
    status: Optional[Literal["open", "under_review", "escalated", "resolved", "closed"]] = None


class CaseTransactionRequest(BaseModel):
    transaction_id: str = Field(min_length=1, max_length=128)


class CaseNoteRequest(BaseModel):
    content: str = Field(min_length=1, max_length=5000)
    author: Optional[str] = Field(default=None, max_length=128)


@router.get("/readiness")
async def readiness():
    return APIResponse(success=True, message="Risk engine readiness.", data=risk_engine.readiness())


@router.post("/assess/bulk")
async def assess_bulk(request: TransactionAssessmentRequest):
    readiness = risk_engine.readiness()
    if not readiness["ready"]:
        raise HTTPException(status_code=409, detail=readiness["message"])
    results = []
    errors = []
    for transaction_id in dict.fromkeys(request.transaction_ids):
        try:
            results.append(risk_engine.assess(transaction_id))
        except HTTPException as exc:
            errors.append({"transaction_id": transaction_id, "status": exc.status_code, "detail": exc.detail})
        except Exception as exc:
            errors.append({"transaction_id": transaction_id, "status": 500, "detail": str(exc)})
    return APIResponse(
        success=True,
        message="Bulk risk assessments completed.",
        data={"assessed": results, "errors": errors, "assessed_count": len(results)},
    )


@router.get("/transactions/{transaction_id}")
async def transaction_assessment(transaction_id: str):
    try:
        data = risk_engine.assess(transaction_id)
    except HTTPException:
        raise
    return APIResponse(success=True, message="Investigation risk assessment.", data=data)


@router.get("/assessments")
async def assessments(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    category: Optional[Literal["critical", "high", "medium", "low"]] = None,
    search: Optional[str] = Query(default=None, max_length=128),
    sort_by: Literal["risk_score", "ml_probability", "transaction_id"] = "risk_score",
    sort_order: Literal["asc", "desc"] = "desc",
):
    data = risk_engine.list_assessments(
        page,
        page_size,
        category,
        search,
        sort_by,
        sort_order,
    )
    return APIResponse(success=True, message="Paginated risk assessments.", data=data)


@router.get("/distribution")
async def distribution():
    return APIResponse(success=True, message="Risk category distribution.", data=risk_engine.distribution())


@router.get("/configuration")
async def configuration():
    return APIResponse(success=True, message="Risk scoring configuration.", data=risk_engine.readiness())


@router.get("/global-factors")
async def global_factors():
    return APIResponse(
        success=True,
        message="Global model and graph risk factors.",
        data={
            "compatibility": risk_engine.compatibility(),
            "model_explanation": (
                risk_engine.compatibility()
                and risk_engine.compatibility()["compatible"]
            ),
            "supported_factors": [
                "ML illicit-risk probability",
                "Graph incoming/outgoing connectivity",
                "Connections to suspicious predicted transactions",
                "Fan-in",
                "Fan-out",
                "Suspicious cluster membership",
            ],
            "unsupported_factors": [
                "Structuring / smurfing",
                "Rapid movement",
                "Amounts",
                "Wallet ownership",
            ],
        },
    )


@router.get("/cases")
async def list_cases(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    status: Optional[Literal["open", "under_review", "escalated", "resolved", "closed"]] = None,
    priority: Optional[Literal["critical", "high", "medium", "low"]] = None,
):
    data = risk_engine.list_cases(page, page_size, status, priority)
    return APIResponse(success=True, message="Investigation cases.", data=data)


@router.post("/cases")
async def create_case(request: CaseCreateRequest):
    data = risk_engine.create_case(
        request.title,
        request.description,
        request.priority,
        request.status,
        request.primary_transaction_id,
        request.transaction_ids,
        request.risk_assessment_reference,
    )
    return APIResponse(success=True, message="Investigation case created.", data=data)


@router.get("/cases/{case_id}")
async def case_details(case_id: str):
    return APIResponse(success=True, message="Investigation case details.", data=risk_engine.get_case(case_id))


@router.patch("/cases/{case_id}")
async def update_case(case_id: str, request: CaseUpdateRequest):
    data = risk_engine.update_case(
        case_id,
        request.title,
        request.description,
        request.priority,
        request.status,
    )
    return APIResponse(success=True, message="Investigation case updated.", data=data)


@router.post("/cases/{case_id}/transactions")
async def add_case_transaction(case_id: str, request: CaseTransactionRequest):
    data = risk_engine.add_transaction(case_id, request.transaction_id)
    return APIResponse(success=True, message="Transaction added to investigation case.", data=data)


@router.delete("/cases/{case_id}/transactions/{transaction_id}")
async def remove_case_transaction(case_id: str, transaction_id: str):
    data = risk_engine.remove_transaction(case_id, transaction_id)
    return APIResponse(success=True, message="Transaction removed from investigation case.", data=data)


@router.post("/cases/{case_id}/notes")
async def add_case_note(case_id: str, request: CaseNoteRequest):
    data = risk_engine.add_note(case_id, request.content, request.author)
    return APIResponse(success=True, message="Investigation note added.", data=data)
