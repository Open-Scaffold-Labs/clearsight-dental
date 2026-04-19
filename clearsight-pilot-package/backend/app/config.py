"""Environment-driven configuration for the ClearSight Dental backend."""
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    database_url: str = Field(..., alias="DATABASE_URL")
    shared_api_secret: str = Field(..., alias="SHARED_API_SECRET")
    frontend_origin: str = Field(..., alias="FRONTEND_ORIGIN")
    pilot_tenant_id: str = Field("dia-basher-dds", alias="PILOT_TENANT_ID")
    audit_log_retention_days: int = Field(2190, alias="AUDIT_LOG_RETENTION_DAYS")
    model_dir: str = Field("/app/models/oralgpt-omni-7b", alias="MODEL_DIR")
    model_name: str = Field("oralgpt-omni-7b", alias="MODEL_NAME")
    max_concurrent: int = Field(1, alias="MAX_CONCURRENT")
    log_level: str = Field("info", alias="LOG_LEVEL")

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
