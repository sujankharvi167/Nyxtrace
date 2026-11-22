from contextlib import asynccontextmanager
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import setup_logging, logger
from app.api import health, analysis, reports, ml, graph, risk
from app.services.dataset_processor import (
    MAX_TOTAL_UPLOAD_SIZE_BYTES,
    MINIMUM_UPLOAD_DISK_RESERVE_BYTES,
)


class UploadStoragePreflightMiddleware:
    def __init__(self, app):
        self.app = app
        self.backend_dir = Path(__file__).resolve().parents[1]

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] == "http"
            and scope["method"] == "POST"
            and scope["path"] == "/api/analysis/upload"
        ):
            headers = dict(scope.get("headers", []))
            content_length = headers.get(b"content-length")
            if content_length:
                try:
                    request_bytes = int(content_length)
                except ValueError:
                    response = JSONResponse(
                        status_code=400,
                        content={"detail": "Invalid Content-Length on dataset upload request."},
                    )
                    await response(scope, receive, send)
                    return

                if request_bytes > MAX_TOTAL_UPLOAD_SIZE_BYTES + 1024 * 1024:
                    response = JSONResponse(
                        status_code=413,
                        content={"detail": "The upload request exceeds the 800 MB combined file limit."},
                    )
                    await response(scope, receive, send)
                    return

                required = {
                    self.backend_dir: request_bytes * 2 + MINIMUM_UPLOAD_DISK_RESERVE_BYTES,
                    Path(tempfile.gettempdir()): request_bytes + MINIMUM_UPLOAD_DISK_RESERVE_BYTES,
                }
                for path, required_bytes in required.items():
                    try:
                        free_bytes = shutil.disk_usage(path).free
                    except OSError as exc:
                        response = JSONResponse(
                            status_code=500,
                            content={"detail": f"Could not verify available upload storage at {path}: {exc}"},
                        )
                        await response(scope, receive, send)
                        return
                    if free_bytes < required_bytes:
                        response = JSONResponse(
                            status_code=507,
                            content={
                                "detail": (
                                    f"Insufficient disk space at {path}. The request needs approximately "
                                    f"{required_bytes // (1024 * 1024)} MB and "
                                    f"{free_bytes // (1024 * 1024)} MB is available."
                                )
                            },
                        )
                        await response(scope, receive, send)
                        return
        await self.app(scope, receive, send)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging("DEBUG" if settings.DEBUG else "INFO")
    logger.info(
        "Starting %s v%s [%s]",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.APP_ENV,
    )
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="ML-Powered Money Laundering Detection & Intelligence Platform",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(UploadStoragePreflightMiddleware)

app.include_router(health.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(ml.router, prefix="/api")
app.include_router(graph.router, prefix="/api")
app.include_router(risk.router, prefix="/api")


@app.get("/")
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "operational",
        "docs": "/api/docs",
    }
