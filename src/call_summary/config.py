"""Infrastructure settings, independent of ASR imports."""

from functools import lru_cache
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: SecretStr
    migration_database_url: SecretStr | None = None
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=2, ge=0, le=50)
    audio_storage_backend: Literal["s3"] = "s3"
    s3_endpoint_url: str
    s3_region: str = "us-east-1"
    s3_bucket: str = "call-audio"
    s3_access_key_id: SecretStr
    s3_secret_access_key: SecretStr
    s3_addressing_style: Literal["path", "virtual"] = "path"
    audio_temp_dir: Path = Path("/tmp/call-summary")
    max_audio_bytes: int = Field(default=104857600, gt=0)
    worker_concurrency: int = Field(default=1, ge=1, le=16)
    worker_max_attempts: int = Field(default=3, ge=1)
    worker_lease_seconds: int = Field(default=120, ge=10)
    transcriber_provider: str = "deepgram"
    diarizer_provider: str = "deepgram"
    deepgram_token: SecretStr | None = None
    llm_provider: str = "unconfigured"
    llm_api_key: SecretStr | None = None
    local_workspace_id: UUID = UUID("00000000-0000-4000-8000-000000000001")


@lru_cache
def get_settings():
    return Settings()
