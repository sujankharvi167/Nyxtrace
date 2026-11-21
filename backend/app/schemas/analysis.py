from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime


class DatasetInfo(BaseModel):
    filename: str
    total_rows: int
    total_columns: int
    columns: List[str]
    missing_values: Dict[str, int]
    dtypes: Dict[str, str]
    file_size_bytes: int
    uploaded_at: datetime


class AnalysisSummary(BaseModel):
    dataset_info: DatasetInfo
    status: str
    message: str


class PlatformStats(BaseModel):
    total_transactions_analyzed: Optional[int] = None
    suspicious_transactions_detected: Optional[int] = None
    accounts_flagged: Optional[int] = None
    active_investigations: int = 0
    last_analysis_at: Optional[datetime] = None
    platform_status: str = "ready"
