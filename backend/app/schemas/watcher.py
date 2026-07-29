from datetime import datetime
from typing import Literal

from pydantic import BaseModel

WatcherLibraryState = Literal[
    "watching",
    "reconciliation_only",
    "disabled",
    "error",
]
WatcherActivityAction = Literal[
    "detected",
    "waiting",
    "scanning",
    "completed",
    "failed",
    "removed",
    "reconciled",
    "started",
    "stopped",
]


class WatcherActivityRead(BaseModel):
    timestamp: datetime
    action: WatcherActivityAction
    message: str
    library_id: str | None = None
    library_name: str | None = None
    relative_path: str | None = None


class WatcherLibraryStatusRead(BaseModel):
    library_id: str
    library_name: str
    root_path: str
    state: WatcherLibraryState
    pending_files: int
    last_event_at: datetime | None = None
    last_reconcile_at: datetime | None = None
    last_error: str | None = None


class WatcherStatusRead(BaseModel):
    enabled: bool
    running: bool
    stability_seconds: int
    reconcile_minutes: int
    pending_files: int
    active_library_id: str | None = None
    active_relative_path: str | None = None
    libraries: list[WatcherLibraryStatusRead]
    recent_activity: list[WatcherActivityRead]


class WatcherCommandRead(BaseModel):
    accepted: bool
    message: str
