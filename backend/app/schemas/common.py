from pydantic import BaseModel
from typing import Any, Optional


class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    service: str
