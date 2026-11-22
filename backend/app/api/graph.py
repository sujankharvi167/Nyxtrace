from fastapi import APIRouter, HTTPException, Query
from starlette.concurrency import run_in_threadpool

from app.schemas.common import APIResponse
from app.services.graph_engine import graph_engine


router = APIRouter(prefix="/graph", tags=["Graph Intelligence"])


@router.get("/status")
async def graph_status():
    return APIResponse(
        success=True,
        message="Graph engine status.",
        data=graph_engine.get_status(),
    )


@router.post("/build")
async def build_graph():
    try:
        data = await run_in_threadpool(graph_engine.build)
        return APIResponse(success=True, message="Graph construction completed.", data=data)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not build graph: {exc}") from exc


@router.get("/statistics")
async def graph_statistics():
    return APIResponse(
        success=True,
        message="Graph network statistics.",
        data=await run_in_threadpool(graph_engine.statistics),
    )


@router.get("/transactions/{transaction_id}")
async def transaction_details(transaction_id: str):
    return APIResponse(
        success=True,
        message="Transaction graph node details.",
        data=await run_in_threadpool(graph_engine.node_details, transaction_id),
    )


@router.get("/neighborhood/{transaction_id}")
async def neighborhood(
    transaction_id: str,
    depth: int = Query(default=2, ge=1, le=10),
    limit: int = Query(default=100, ge=1, le=500),
    direction: str = Query(default="all", pattern="^(all|upstream|downstream)$"),
):
    data = await run_in_threadpool(
        graph_engine.neighborhood,
        transaction_id,
        depth,
        limit,
        direction,
    )
    return APIResponse(success=True, message="Bounded transaction neighborhood.", data=data)


@router.get("/traces/upstream/{transaction_id}")
async def upstream_trace(
    transaction_id: str,
    depth: int = Query(default=3, ge=1, le=10),
    limit: int = Query(default=100, ge=1, le=500),
):
    data = await run_in_threadpool(
        graph_engine.neighborhood,
        transaction_id,
        depth,
        limit,
        "upstream",
    )
    return APIResponse(success=True, message="Upstream transaction trace.", data=data)


@router.get("/traces/downstream/{transaction_id}")
async def downstream_trace(
    transaction_id: str,
    depth: int = Query(default=3, ge=1, le=10),
    limit: int = Query(default=100, ge=1, le=500),
):
    data = await run_in_threadpool(
        graph_engine.neighborhood,
        transaction_id,
        depth,
        limit,
        "downstream",
    )
    return APIResponse(success=True, message="Downstream transaction trace.", data=data)


@router.get("/path")
async def shortest_path(
    source: str = Query(..., min_length=1),
    destination: str = Query(..., min_length=1),
    limit: int = Query(default=100, ge=1, le=500),
):
    data = await run_in_threadpool(
        graph_engine.shortest_path,
        source,
        destination,
        limit,
    )
    return APIResponse(success=True, message="Shortest transaction relationship path.", data=data)


@router.get("/patterns/fan-in")
async def fan_in(limit: int = Query(default=25, ge=1, le=500)):
    return APIResponse(
        success=True,
        message="Transactions receiving multiple incoming relationships.",
        data=await run_in_threadpool(graph_engine.fan_in, limit),
    )


@router.get("/patterns/fan-out")
async def fan_out(limit: int = Query(default=25, ge=1, le=500)):
    return APIResponse(
        success=True,
        message="Transactions connecting to multiple outgoing relationships.",
        data=await run_in_threadpool(graph_engine.fan_out, limit),
    )


@router.get("/patterns/cycles")
async def cycles(limit: int = Query(default=25, ge=1, le=25)):
    return APIResponse(
        success=True,
        message="Bounded circular relationship detection.",
        data=await run_in_threadpool(graph_engine.cycles, limit),
    )


@router.get("/patterns/clusters")
async def suspicious_clusters(limit: int = Query(default=25, ge=1, le=500)):
    return APIResponse(
        success=True,
        message="Connected groups containing multiple ML-flagged transactions.",
        data=await run_in_threadpool(graph_engine.suspicious_clusters, limit),
    )
