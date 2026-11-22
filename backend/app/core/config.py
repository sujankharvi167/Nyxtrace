from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    APP_NAME: str = "NyxTrace"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8001
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    RISK_ASSESSMENT_VERSION: str = "nyxtrace-risk-v1"
    RISK_ML_WEIGHT: float = 0.70
    RISK_GRAPH_CONNECTIVITY_WEIGHT: float = 0.10
    RISK_GRAPH_SUSPICIOUS_NEIGHBOR_WEIGHT: float = 0.10
    RISK_PATTERN_WEIGHT: float = 0.10

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
