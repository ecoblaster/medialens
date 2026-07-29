from __future__ import annotations

import time
import traceback

from sqlalchemy import select

from app.db.base import utc_now
from app.db.session import SessionLocal
from app.models.enums import ScanRunStatus
from app.models.library import Library
from app.models.media import MediaFile
from app.models.scan import ScanRun
from app.services.probe import ProbeCancelled, finish_probe_operation, probe_operation
from app.services.scan_progress import (
    begin_scan_file,
    clear_scan_progress,
    complete_scan_file,
    set_scan_stage,
)
from app.services.scanner import _record_file_failure, _scan_file, discover_library_files


def _mark_cancelled(db, scan_run: ScanRun) -> None:
    scan_run.status = ScanRunStatus.CANCELLED.value
    scan_run.completed_at = scan_run.completed_at or utc_now()
    scan_run.error_message = None
    db.commit()


def _reload_scan(db, scan_id: str) -> ScanRun | None:
    """Reload a scan only when the current transaction has no pending work."""
    db.expire_all()
    return db.get(ScanRun, scan_id)


def _is_cancelled(scan_run: ScanRun | None) -> bool:
    return scan_run is None or scan_run.status in {
        ScanRunStatus.CANCELLING.value,
        ScanRunStatus.CANCELLED.value,
    }


def _cancel_requested(scan_id: str) -> bool:
    """Read cancellation state without expiring the worker transaction.

    The worker may have uncommitted counter and file-result changes. Calling
    expire_all() at that point discards changes such as files_analyzed += 1.
    A separate short-lived session preserves the active transaction while still
    allowing the worker to observe a cancellation request.
    """
    with SessionLocal() as status_db:
        status = status_db.scalar(select(ScanRun.status).where(ScanRun.id == scan_id))
    return status is None or status in {
        ScanRunStatus.CANCELLING.value,
        ScanRunStatus.CANCELLED.value,
    }


def _mark_worker_failed(scan_id: str, error: BaseException) -> None:
    try:
        with SessionLocal() as db:
            scan_run = db.get(ScanRun, scan_id)
            if scan_run is None or scan_run.status == ScanRunStatus.CANCELLED.value:
                return
            scan_run.status = ScanRunStatus.FAILED.value
            scan_run.completed_at = utc_now()
            scan_run.error_message = (
                f"Background scan worker crashed: {type(error).__name__}: {error}"
            )
            db.commit()
    except Exception:
        traceback.print_exc()


def run_library_scan_background(scan_id: str, force: bool = False) -> None:
    try:
        with SessionLocal() as db:
            scan_run = db.get(ScanRun, scan_id)
            if scan_run is None:
                return
            if _is_cancelled(scan_run):
                _mark_cancelled(db, scan_run)
                return

            library = db.get(Library, scan_run.library_id)
            if library is None:
                scan_run.status = ScanRunStatus.FAILED.value
                scan_run.error_message = "The library was deleted before the scan started."
                scan_run.completed_at = utc_now()
                db.commit()
                return

            try:
                set_scan_stage(scan_id, "Discovering media files")
                discovered = discover_library_files(library)
            except Exception as exc:
                db.rollback()
                scan_run = _reload_scan(db, scan_id)
                if _is_cancelled(scan_run):
                    if scan_run is not None:
                        _mark_cancelled(db, scan_run)
                    return
                scan_run.status = ScanRunStatus.FAILED.value
                scan_run.error_message = str(exc)
                scan_run.completed_at = utc_now()
                db.commit()
                return

            scan_run = _reload_scan(db, scan_id)
            if _is_cancelled(scan_run):
                if scan_run is not None:
                    _mark_cancelled(db, scan_run)
                return

            scan_run.status = ScanRunStatus.RUNNING.value
            scan_run.started_at = utc_now()
            scan_run.files_discovered = len(discovered)
            db.commit()
            set_scan_stage(scan_id, "Preparing first file")

            for media_path, canonical_relative in discovered:
                # This reload is safe because the previous file transaction has
                # already committed or rolled back.
                scan_run = _reload_scan(db, scan_id)
                library = db.get(Library, scan_run.library_id) if scan_run else None
                if scan_run is None or library is None:
                    return
                if _is_cancelled(scan_run):
                    _mark_cancelled(db, scan_run)
                    return

                started = time.monotonic()
                begin_scan_file(scan_id, canonical_relative)
                existing = db.scalar(
                    select(MediaFile).where(
                        MediaFile.library_id == library.id,
                        MediaFile.relative_path == canonical_relative,
                    )
                )
                existing_id = existing.id if existing else None
                completed_for_eta = False

                try:
                    with probe_operation(scan_id):
                        _scan_file(
                            db,
                            scan_run,
                            library,
                            media_path,
                            canonical_relative,
                            force=force,
                        )

                    # Do not reload or expire the worker session here. _scan_file
                    # has pending counter increments and ScanFileResult objects
                    # that must be committed. Check cancellation separately.
                    if _cancel_requested(scan_id):
                        db.rollback()
                        latest = _reload_scan(db, scan_id)
                        if latest is not None:
                            _mark_cancelled(db, latest)
                        return

                    set_scan_stage(scan_id, "Saving metadata")
                    db.commit()
                    completed_for_eta = True

                except ProbeCancelled:
                    db.rollback()
                    latest = _reload_scan(db, scan_id)
                    if latest is not None:
                        _mark_cancelled(db, latest)
                    return

                except Exception as exc:
                    # SQLAlchemy sessions are unusable after flush/commit errors
                    # until rollback is called. Roll back before any status query.
                    db.rollback()
                    latest = _reload_scan(db, scan_id)
                    if _is_cancelled(latest):
                        if latest is not None:
                            _mark_cancelled(db, latest)
                        return

                    _record_file_failure(
                        db,
                        scan_id=scan_id,
                        library_id=library.id,
                        relative_path=canonical_relative,
                        existing_file_id=existing_id,
                        started=started,
                        error=exc,
                    )
                    completed_for_eta = True

                finally:
                    if completed_for_eta:
                        complete_scan_file(scan_id, time.monotonic() - started)

            scan_run = _reload_scan(db, scan_id)
            library = db.get(Library, scan_run.library_id) if scan_run else None
            if scan_run is None:
                return
            if _is_cancelled(scan_run):
                _mark_cancelled(db, scan_run)
                return

            scan_run.status = (
                ScanRunStatus.PARTIAL.value
                if scan_run.files_failed
                else ScanRunStatus.COMPLETED.value
            )
            scan_run.completed_at = utc_now()
            if library is not None:
                library.last_scan_at = scan_run.completed_at
            db.commit()

    except BaseException as exc:
        traceback.print_exc()
        _mark_worker_failed(scan_id, exc)
    finally:
        finish_probe_operation(scan_id)
        clear_scan_progress(scan_id)
