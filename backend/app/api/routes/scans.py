from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.base import utc_now
from app.db.session import get_db
from app.models.enums import ScanRunStatus
from app.models.library import Library
from app.models.scan import ScanRun
from app.schemas.scan import ScanCreate, ScanRead
from app.services.probe import cancel_probe_operation
from app.services.scan_progress import get_scan_progress, mark_scan_cancelling
from app.services.scanner import ScanValidationError, queue_library_scan, scan_single_file
from app.services.scanner_background import run_library_scan_background

router = APIRouter(prefix="/scans", tags=["scans"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def _scan_query():
    return select(ScanRun).options(selectinload(ScanRun.file_results))


def _scan_read(scan: ScanRun) -> ScanRead:
    result = ScanRead.model_validate(scan)
    progress = get_scan_progress(scan.id)
    if progress is None:
        return result
    processed = scan.files_analyzed + scan.files_skipped + scan.files_failed
    remaining = max(scan.files_discovered - processed, 0)
    average = progress.average_seconds_per_file
    return result.model_copy(
        update={
            "current_relative_path": progress.current_relative_path,
            "current_filename": progress.current_filename,
            "current_stage": progress.current_stage,
            "current_file_started_at": progress.current_file_started_at,
            "current_stage_started_at": progress.current_stage_started_at,
            "average_seconds_per_file": round(average, 2) if average is not None else None,
            "estimated_remaining_seconds": round(average * remaining, 1) if average is not None else None,
        }
    )


@router.post("", response_model=ScanRead, status_code=status.HTTP_201_CREATED)
def create_scan(payload: ScanCreate, background_tasks: BackgroundTasks, db: DatabaseSession) -> ScanRead:
    library = db.get(Library, payload.library_id)
    if library is None:
        raise HTTPException(status_code=404, detail={"code": "LIBRARY_NOT_FOUND", "message": "The requested library does not exist.", "details": {"library_id": payload.library_id}})
    try:
        if payload.mode == "full":
            scan = queue_library_scan(db, library)
            background_tasks.add_task(run_library_scan_background, scan.id, payload.force)
        else:
            scan = scan_single_file(db, library, payload.relative_path or "", force=payload.force)
    except ScanValidationError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message, "details": exc.details}) from exc
    loaded = db.scalar(_scan_query().where(ScanRun.id == scan.id))
    return _scan_read(loaded)


@router.get("", response_model=list[ScanRead])
def list_scans(db: DatabaseSession, library_id: str | None = None, limit: Annotated[int, Query(ge=1, le=100)] = 25) -> list[ScanRead]:
    query = _scan_query().order_by(ScanRun.started_at.desc()).limit(limit)
    if library_id:
        query = query.where(ScanRun.library_id == library_id)
    return [_scan_read(scan) for scan in db.scalars(query).unique().all()]


@router.post("/{scan_id}/cancel", response_model=ScanRead)
def cancel_scan(scan_id: str, db: DatabaseSession) -> ScanRead:
    scan = db.scalar(_scan_query().where(ScanRun.id == scan_id))
    if scan is None:
        raise HTTPException(status_code=404, detail={"code": "SCAN_NOT_FOUND", "message": "The requested scan does not exist.", "details": {"scan_id": scan_id}})

    # Cancellation is authoritative at the API boundary. The UI and database do
    # not wait for a worker that may be blocked in filesystem or native-tool I/O.
    if scan.status == ScanRunStatus.CANCELLED.value:
        return _scan_read(scan)
    if scan.status not in {
        ScanRunStatus.QUEUED.value,
        ScanRunStatus.RUNNING.value,
        ScanRunStatus.CANCELLING.value,
    }:
        raise HTTPException(status_code=409, detail={"code": "SCAN_NOT_CANCELLABLE", "message": "Only queued or running scans can be cancelled.", "details": {"scan_id": scan_id, "status": scan.status}})

    mark_scan_cancelling(scan_id)
    cancel_probe_operation(scan_id)
    scan.status = ScanRunStatus.CANCELLED.value
    scan.completed_at = utc_now()
    scan.error_message = None
    db.commit()

    loaded = db.scalar(_scan_query().where(ScanRun.id == scan.id))
    return _scan_read(loaded)


@router.get("/{scan_id}", response_model=ScanRead)
def read_scan(scan_id: str, db: DatabaseSession) -> ScanRead:
    scan = db.scalar(_scan_query().where(ScanRun.id == scan_id))
    if scan is None:
        raise HTTPException(status_code=404, detail={"code": "SCAN_NOT_FOUND", "message": "The requested scan does not exist.", "details": {"scan_id": scan_id}})
    return _scan_read(scan)
