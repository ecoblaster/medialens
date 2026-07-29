from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path

from app.db.base import utc_now


@dataclass
class ScanProgress:
    current_relative_path: str | None = None
    current_filename: str | None = None
    current_stage: str | None = None
    current_file_started_at: datetime | None = None
    current_stage_started_at: datetime | None = None
    updated_at: datetime | None = None
    completed_files: int = 0
    completed_file_seconds: float = 0.0

    @property
    def average_seconds_per_file(self) -> float | None:
        if self.completed_files <= 0:
            return None
        return self.completed_file_seconds / self.completed_files


_lock = threading.Lock()
_progress_by_scan: dict[str, ScanProgress] = {}
_progress_dir = Path("/data/scan-progress")


def _get_or_create(scan_id: str) -> ScanProgress:
    progress = _progress_by_scan.get(scan_id)
    if progress is None:
        progress = _read_progress_file(scan_id) or ScanProgress()
        _progress_by_scan[scan_id] = progress
    return progress


def _progress_path(scan_id: str) -> Path:
    # Scan IDs are generated UUIDs, but keep the path safe if this ever changes.
    safe_id = "".join(character for character in scan_id if character.isalnum() or character in {"-", "_"})
    return _progress_dir / f"{safe_id}.json"


def _serialize(progress: ScanProgress) -> dict[str, object]:
    payload = asdict(progress)
    for key in ("current_file_started_at", "current_stage_started_at", "updated_at"):
        value = payload.get(key)
        if isinstance(value, datetime):
            payload[key] = value.isoformat()
    return payload


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _read_progress_file(scan_id: str) -> ScanProgress | None:
    path = _progress_path(scan_id)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return ScanProgress(
        current_relative_path=payload.get("current_relative_path") if isinstance(payload.get("current_relative_path"), str) else None,
        current_filename=payload.get("current_filename") if isinstance(payload.get("current_filename"), str) else None,
        current_stage=payload.get("current_stage") if isinstance(payload.get("current_stage"), str) else None,
        current_file_started_at=_parse_datetime(payload.get("current_file_started_at")),
        current_stage_started_at=_parse_datetime(payload.get("current_stage_started_at")),
        updated_at=_parse_datetime(payload.get("updated_at")),
        completed_files=int(payload.get("completed_files") or 0),
        completed_file_seconds=float(payload.get("completed_file_seconds") or 0.0),
    )


def _write_progress_file(scan_id: str, progress: ScanProgress) -> None:
    # Progress reporting must never be able to crash a media scan.
    try:
        _progress_dir.mkdir(parents=True, exist_ok=True)
        destination = _progress_path(scan_id)
        temporary = destination.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(_serialize(progress), separators=(",", ":")), encoding="utf-8")
        temporary.replace(destination)
    except OSError:
        pass


def _save(scan_id: str, progress: ScanProgress) -> None:
    progress.updated_at = utc_now()
    _write_progress_file(scan_id, progress)


def set_scan_stage(scan_id: str, stage: str) -> None:
    now = utc_now()
    with _lock:
        progress = _get_or_create(scan_id)
        if progress.current_stage != stage:
            progress.current_stage = stage
            progress.current_stage_started_at = now
        _save(scan_id, progress)


def begin_scan_file(scan_id: str, relative_path: str) -> None:
    now = utc_now()
    with _lock:
        progress = _get_or_create(scan_id)
        progress.current_relative_path = relative_path
        progress.current_filename = Path(relative_path).name
        progress.current_stage = "Checking file"
        progress.current_file_started_at = now
        progress.current_stage_started_at = now
        _save(scan_id, progress)


def complete_scan_file(scan_id: str, duration_seconds: float) -> None:
    now = utc_now()
    with _lock:
        progress = _get_or_create(scan_id)
        progress.completed_files += 1
        progress.completed_file_seconds += max(duration_seconds, 0.0)
        progress.current_relative_path = None
        progress.current_filename = None
        progress.current_file_started_at = None
        progress.current_stage = "Preparing next file"
        progress.current_stage_started_at = now
        _save(scan_id, progress)


def mark_scan_cancelling(scan_id: str) -> None:
    set_scan_stage(scan_id, "Cancelling active probe")


def get_scan_progress(scan_id: str) -> ScanProgress | None:
    with _lock:
        progress = _progress_by_scan.get(scan_id)
        if progress is None:
            progress = _read_progress_file(scan_id)
            if progress is not None:
                _progress_by_scan[scan_id] = progress
        return replace(progress) if progress is not None else None


def clear_scan_progress(scan_id: str) -> None:
    with _lock:
        _progress_by_scan.pop(scan_id, None)
        try:
            _progress_path(scan_id).unlink(missing_ok=True)
        except OSError:
            pass
