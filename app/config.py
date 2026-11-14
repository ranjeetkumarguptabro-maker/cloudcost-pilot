"""Configuration management for CloudCost Pilot."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator


class Settings(BaseModel):
    """Application settings loaded from environment variables and defaults."""

    # AWS Configuration
    aws_profile: str | None = Field(
        default=None,
        description=(
            "Named AWS CLI profile to use. If None, uses default credential chain."
        ),
    )
    aws_default_region: str = Field(
        default="us-east-1",
        description="Default AWS region for infrastructure resource queries.",
    )
    cost_explorer_region: str = Field(
        default="us-east-1",
        description=(
            "AWS region for Cost Explorer API endpoint "
            "(Cost Explorer is hosted in us-east-1)."
        ),
    )

    # Logging Configuration
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging verbosity level.",
    )
    log_format: Literal["json", "text"] = Field(
        default="json",
        description=(
            "Format for log messages (json for structured logging, "
            "text for human-readable)."
        ),
    )

    # Storage Paths
    data_dir: Path = Field(
        default=Path("data"),
        description="Directory for storing collected JSON data and raw extracts.",
    )
    reports_dir: Path = Field(
        default=Path("reports"),
        description="Directory for storing generated cost reports and summaries.",
    )

    @field_validator("data_dir", "reports_dir", mode="before")
    @classmethod
    def parse_path(cls, v: str | Path) -> Path:
        """Ensure paths are resolved as Path objects."""
        return Path(v) if isinstance(v, str) else v

    def ensure_directories(self) -> None:
        """Create configured data and reports directories if they do not exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls, env_file: str | Path | None = None) -> Settings:
        """Load configuration from .env file (if present) and environment variables."""
        if env_file:
            load_dotenv(dotenv_path=env_file, override=True)
        else:
            load_dotenv(override=False)

        profile = os.getenv("AWS_PROFILE") or None
        default_region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        ce_region = os.getenv("COST_EXPLORER_REGION", "us-east-1")
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        log_format = os.getenv("LOG_FORMAT", "json").lower()
        data_dir = os.getenv("DATA_DIR", "data")
        reports_dir = os.getenv("REPORTS_DIR", "reports")

        return cls(
            aws_profile=profile,
            aws_default_region=default_region,
            cost_explorer_region=ce_region,
            log_level=log_level,  # type: ignore[arg-type]
            log_format=log_format,  # type: ignore[arg-type]
            data_dir=Path(data_dir),
            reports_dir=Path(reports_dir),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retrieve cached application settings instance."""
    settings = Settings.from_env()
    settings.ensure_directories()
    return settings
