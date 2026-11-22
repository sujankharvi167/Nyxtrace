from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.schemas.common import APIResponse
from app.services.report_engine import report_engine


router = APIRouter(prefix="/reports", tags=["Reports"])


class ReportGenerateRequest(BaseModel):
    report_name: str = Field(min_length=1, max_length=200)
    report_type: Literal[
        "transaction_summary",
        "ml_detection",
        "network_analysis",
        "investigation_brief",
        "risk_dashboard",
        "compliance_export",
    ]
    investigation_case_id: Optional[str] = Field(default=None, max_length=128)
    transaction_ids: list[str] = Field(default_factory=list, max_length=500)


@router.get("/types")
async def report_types():
    return APIResponse(
        success=True,
        message="Available report types.",
        data={"types": report_engine.list_types()},
    )


@router.post("/generate")
async def generate_report(request: ReportGenerateRequest):
    try:
        data = await run_in_threadpool(
            report_engine.generate,
            request.report_name,
            request.report_type,
            request.investigation_case_id,
            request.transaction_ids,
        )
        return APIResponse(success=True, message="PDF report generated.", data=data)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not generate report: {exc}") from exc


@router.get("")
async def list_reports(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    report_type: Optional[str] = Query(default=None, max_length=64),
    investigation_case_id: Optional[str] = Query(default=None, max_length=128),
):
    data = report_engine.list_reports(
        page,
        page_size,
        report_type,
        investigation_case_id,
    )
    return APIResponse(success=True, message="Generated report history.", data=data)


@router.get("/{report_id}")
async def report_metadata(report_id: str):
    return APIResponse(
        success=True,
        message="Report metadata.",
        data=report_engine.get_report(report_id),
    )


@router.get("/{report_id}/download")
async def download_report(report_id: str):
    path = report_engine.get_download_path(report_id)
    report = report_engine.get_report(report_id)
    safe_download_name = report_engine._safe_report_name(report["report_name"]) + ".pdf"
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=safe_download_name,
    )
