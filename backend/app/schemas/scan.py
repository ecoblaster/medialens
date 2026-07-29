from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScanCreate(BaseModel):
    library_id: str
    mode: Literal["single_file", "full"] = "single_file"
    relative_path: str | None = Field(default=None, min_length=1, max_length=4096)
    force: bool = False

    @model_validator(mode="after")
    def validate_mode_and_path(self) -> "ScanCreate":
        if self.mode == "single_file" and not self.relative_path:
            raise ValueError("relative_path is required for single_file scans")
        if self.mode == "full" and self.relative_path:
            raise ValueError("relative_path must be omitted for full scans")
        if self.relative_path:
            normalized = self.relative_path.replace("\\", "/")
            if normalized.startswith("/"):
                raise ValueError("relative_path must not be absolute")
            if ".." in normalized.split("/"):
                raise ValueError("relative_path must not contain parent traversal")
        return self


class ScanFileResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    media_file_id: str | None
    relative_path: str
    status: str
    metadata_changed: bool
    duration_ms: int | None
    error_message: str | None


class ScanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    library_id: str
    mode: str
    status: str
    requested_relative_path: str | None
    files_discovered: int
    files_analyzed: int
    files_skipped: int
    files_failed: int
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    app_version: str
    file_results: list[ScanFileResultRead]
    current_relative_path: str | None = None
    current_filename: str | None = None
    current_stage: str | None = None
    current_file_started_at: datetime | None = None
    current_stage_started_at: datetime | None = None
    average_seconds_per_file: float | None = None
    estimated_remaining_seconds: float | None = None
