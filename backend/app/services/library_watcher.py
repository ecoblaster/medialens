from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.enums import ScanRunStatus
from app.models.library import Library
from app.models.media import MediaFile, MediaItem
from app.models.scan import ScanRun
from app.schemas.watcher import (
    WatcherActivityRead,
    WatcherLibraryStatusRead,
    WatcherStatusRead,
)
from app.services.scanner import SUPPORTED_EXTENSIONS, scan_single_file

logger = logging.getLogger(__name__)

_ACTIVE_SCAN_STATES = {
    ScanRunStatus.QUEUED.value,
    ScanRunStatus.RUNNING.value,
    ScanRunStatus.CANCELLING.value,
}
_IGNORED_SUFFIXES = {".part", ".partial", ".tmp", ".temp", ".crdownload"}
_IGNORED_NAME_PARTS = {".!qb", ".sample."}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _is_supported(path: Path) -> bool:
    lowered = path.name.casefold()
    if path.suffix.casefold() not in SUPPORTED_EXTENSIONS:
        return False
    if path.suffix.casefold() in _IGNORED_SUFFIXES:
        return False
    return not any(token in lowered for token in _IGNORED_NAME_PARTS)


@dataclass
class PendingFile:
    library_id: str
    library_name: str
    root_path: Path
    relative_path: str
    absolute_path: Path
    last_size: int | None = None
    last_mtime_ns: int | None = None
    unchanged_since: float | None = None
    queued_at: float = 0.0


@dataclass
class LibraryRuntime:
    library_id: str
    library_name: str
    root_path: Path
    state: str = "watching"
    pending_files: int = 0
    last_event_at: datetime | None = None
    last_reconcile_at: datetime | None = None
    last_error: str | None = None


class LibraryEventHandler(FileSystemEventHandler):
    def __init__(self, manager: "LibraryWatcherManager", library_id: str) -> None:
        self.manager = manager
        self.library_id = library_id

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self.manager.handle_path_event(self.library_id, Path(event.src_path))

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self.manager.handle_path_event(self.library_id, Path(event.src_path))

    def on_moved(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            destination = getattr(event, "dest_path", None)
            if destination:
                self.manager.handle_path_event(self.library_id, Path(destination))

    def on_deleted(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self.manager.handle_deleted_path(self.library_id, Path(event.src_path))


class LibraryWatcherManager:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._observers: dict[str, Observer] = {}
        self._libraries: dict[str, LibraryRuntime] = {}
        self._pending: dict[tuple[str, str], PendingFile] = {}
        self._activity: deque[WatcherActivityRead] = deque(maxlen=100)
        self._running = False
        self._active_library_id: str | None = None
        self._active_relative_path: str | None = None
        self._last_global_reconcile = 0.0

    def start(self) -> None:
        if not settings.auto_scan_enabled:
            self._record("stopped", "Automatic scanning is disabled by configuration.")
            return
        with self._lock:
            if self._running:
                return
            self._stop_event.clear()
            self._running = True
        self._load_libraries()
        self._worker = threading.Thread(
            target=self._run_loop,
            name="medialens-library-watcher",
            daemon=True,
        )
        self._worker.start()
        self._record("started", "Automatic library scanning started.")

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                return
            self._running = False
            self._stop_event.set()
            observers = list(self._observers.values())
            self._observers.clear()
        for observer in observers:
            observer.stop()
        for observer in observers:
            observer.join(timeout=5)
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=10)
        self._record("stopped", "Automatic library scanning stopped.")

    def refresh_libraries(self) -> None:
        self._load_libraries()
        self.reconcile_all()

    def reconcile_all(self) -> None:
        with self._lock:
            library_ids = list(self._libraries)
        for library_id in library_ids:
            self._reconcile_library(library_id)
        self._last_global_reconcile = time.monotonic()

    def handle_path_event(self, library_id: str, path: Path) -> None:
        runtime = self._runtime(library_id)
        if runtime is None or not _is_supported(path):
            return
        try:
            resolved = path.resolve(strict=False)
            if not resolved.is_relative_to(runtime.root_path):
                return
            relative = resolved.relative_to(runtime.root_path).as_posix()
        except (OSError, ValueError):
            return
        self._queue_pending(runtime, resolved, relative, "Filesystem event detected")

    def handle_deleted_path(self, library_id: str, path: Path) -> None:
        runtime = self._runtime(library_id)
        if runtime is None:
            return
        try:
            relative = path.resolve(strict=False).relative_to(runtime.root_path).as_posix()
        except (OSError, ValueError):
            return
        with self._lock:
            self._pending.pop((library_id, relative), None)
        self._remove_missing_metadata(library_id, relative, runtime)

    def status(self) -> WatcherStatusRead:
        with self._lock:
            pending_count = len(self._pending)
            libraries = [
                WatcherLibraryStatusRead(
                    library_id=runtime.library_id,
                    library_name=runtime.library_name,
                    root_path=str(runtime.root_path),
                    state=runtime.state,
                    pending_files=sum(
                        1 for item in self._pending.values() if item.library_id == runtime.library_id
                    ),
                    last_event_at=runtime.last_event_at,
                    last_reconcile_at=runtime.last_reconcile_at,
                    last_error=runtime.last_error,
                )
                for runtime in sorted(self._libraries.values(), key=lambda value: value.library_name.casefold())
            ]
            return WatcherStatusRead(
                enabled=settings.auto_scan_enabled,
                running=self._running,
                stability_seconds=settings.file_stability_seconds,
                reconcile_minutes=settings.reconcile_minutes,
                pending_files=pending_count,
                active_library_id=self._active_library_id,
                active_relative_path=self._active_relative_path,
                libraries=libraries,
                recent_activity=list(self._activity),
            )

    def _runtime(self, library_id: str) -> LibraryRuntime | None:
        with self._lock:
            return self._libraries.get(library_id)

    def _record(
        self,
        action: str,
        message: str,
        runtime: LibraryRuntime | None = None,
        relative_path: str | None = None,
    ) -> None:
        activity = WatcherActivityRead(
            timestamp=_utc_now(),
            action=action,
            message=message,
            library_id=runtime.library_id if runtime else None,
            library_name=runtime.library_name if runtime else None,
            relative_path=relative_path,
        )
        with self._lock:
            self._activity.appendleft(activity)
        logger.info("Auto scan: %s", message)

    def _load_libraries(self) -> None:
        with SessionLocal() as db:
            libraries = list(
                db.scalars(
                    select(Library).where(
                        Library.enabled.is_(True),
                        Library.source_type == "filesystem",
                    )
                )
            )
        desired: dict[str, tuple[str, Path]] = {}
        for library in libraries:
            try:
                root = Path(library.root_path).resolve(strict=True)
                if not root.is_dir():
                    raise NotADirectoryError(str(root))
                desired[library.id] = (library.name, root)
            except OSError as exc:
                runtime = LibraryRuntime(
                    library_id=library.id,
                    library_name=library.name,
                    root_path=Path(library.root_path),
                    state="error",
                    last_error=str(exc),
                )
                with self._lock:
                    self._libraries[library.id] = runtime
                self._record("failed", f"Cannot watch {library.name}: {exc}", runtime)

        with self._lock:
            stale_ids = set(self._observers) - set(desired)
        for library_id in stale_ids:
            with self._lock:
                observer = self._observers.pop(library_id, None)
                self._libraries.pop(library_id, None)
            if observer:
                observer.stop()
                observer.join(timeout=5)

        for library_id, (name, root) in desired.items():
            with self._lock:
                existing = self._libraries.get(library_id)
                observer_exists = library_id in self._observers
            if existing and observer_exists and existing.root_path == root:
                existing.library_name = name
                continue
            runtime = LibraryRuntime(library_id=library_id, library_name=name, root_path=root)
            observer = Observer()
            try:
                observer.schedule(LibraryEventHandler(self, library_id), str(root), recursive=True)
                observer.start()
                runtime.state = "watching"
                with self._lock:
                    old = self._observers.pop(library_id, None)
                    self._observers[library_id] = observer
                    self._libraries[library_id] = runtime
                if old:
                    old.stop()
                    old.join(timeout=5)
            except Exception as exc:
                runtime.state = "reconciliation_only"
                runtime.last_error = f"Filesystem events unavailable: {exc}"
                with self._lock:
                    self._libraries[library_id] = runtime
                self._record(
                    "failed",
                    f"{name} is using reconciliation-only mode because filesystem events failed: {exc}",
                    runtime,
                )

        self.reconcile_all()

    def _queue_pending(
        self,
        runtime: LibraryRuntime,
        absolute_path: Path,
        relative_path: str,
        reason: str,
    ) -> None:
        key = (runtime.library_id, relative_path)
        now = time.monotonic()
        with self._lock:
            is_new = key not in self._pending
            self._pending[key] = PendingFile(
                library_id=runtime.library_id,
                library_name=runtime.library_name,
                root_path=runtime.root_path,
                relative_path=relative_path,
                absolute_path=absolute_path,
                queued_at=now,
            )
            runtime.last_event_at = _utc_now()
        if is_new:
            self._record("detected", f"{reason}: {relative_path}", runtime, relative_path)

    def _run_loop(self) -> None:
        while not self._stop_event.wait(5):
            try:
                interval = max(settings.reconcile_minutes * 60, 60)
                if time.monotonic() - self._last_global_reconcile >= interval:
                    self.reconcile_all()
                self._process_pending()
            except Exception:
                logger.exception("Automatic library watcher loop failed")

    def _manual_or_full_scan_active(self) -> bool:
        with SessionLocal() as db:
            return db.scalar(
                select(ScanRun.id).where(ScanRun.status.in_(_ACTIVE_SCAN_STATES)).limit(1)
            ) is not None

    def _process_pending(self) -> None:
        if self._manual_or_full_scan_active():
            return
        with self._lock:
            pending_items = sorted(self._pending.values(), key=lambda item: item.queued_at)
        for pending in pending_items:
            if self._stop_event.is_set() or self._manual_or_full_scan_active():
                return
            key = (pending.library_id, pending.relative_path)
            runtime = self._runtime(pending.library_id)
            if runtime is None:
                with self._lock:
                    self._pending.pop(key, None)
                continue
            try:
                stat = pending.absolute_path.stat()
                if not pending.absolute_path.is_file() or not _is_supported(pending.absolute_path):
                    with self._lock:
                        self._pending.pop(key, None)
                    continue
            except FileNotFoundError:
                with self._lock:
                    self._pending.pop(key, None)
                self._remove_missing_metadata(pending.library_id, pending.relative_path, runtime)
                continue
            except OSError as exc:
                runtime.last_error = str(exc)
                continue

            now = time.monotonic()
            if pending.last_size != stat.st_size or pending.last_mtime_ns != stat.st_mtime_ns:
                pending.last_size = stat.st_size
                pending.last_mtime_ns = stat.st_mtime_ns
                pending.unchanged_since = now
                self._record(
                    "waiting",
                    f"Waiting for file copy to become stable: {pending.relative_path}",
                    runtime,
                    pending.relative_path,
                )
                continue
            if pending.unchanged_since is None:
                pending.unchanged_since = now
                continue
            if now - pending.unchanged_since < settings.file_stability_seconds:
                continue

            self._scan_pending(pending, runtime)
            with self._lock:
                self._pending.pop(key, None)
            return

    def _scan_pending(self, pending: PendingFile, runtime: LibraryRuntime) -> None:
        self._active_library_id = pending.library_id
        self._active_relative_path = pending.relative_path
        self._record(
            "scanning",
            f"Automatically scanning {pending.relative_path}",
            runtime,
            pending.relative_path,
        )
        try:
            with SessionLocal() as db:
                library = db.get(Library, pending.library_id)
                if library is None or not library.enabled:
                    return
                scan = scan_single_file(db, library, pending.relative_path, force=False)
                if scan.status == ScanRunStatus.COMPLETED.value:
                    self._record(
                        "completed",
                        f"Automatic scan completed: {pending.relative_path}",
                        runtime,
                        pending.relative_path,
                    )
                else:
                    message = scan.error_message or "Automatic scan failed."
                    runtime.last_error = message
                    self._record(
                        "failed",
                        f"Automatic scan failed for {pending.relative_path}: {message}",
                        runtime,
                        pending.relative_path,
                    )
        except Exception as exc:
            runtime.last_error = str(exc)
            self._record(
                "failed",
                f"Automatic scan failed for {pending.relative_path}: {exc}",
                runtime,
                pending.relative_path,
            )
            logger.exception("Automatic scan failed for %s", pending.relative_path)
        finally:
            self._active_library_id = None
            self._active_relative_path = None

    def _reconcile_library(self, library_id: str) -> None:
        runtime = self._runtime(library_id)
        if runtime is None:
            return
        try:
            discovered: dict[str, Path] = {}
            for path in runtime.root_path.rglob("*"):
                if path.is_file() and _is_supported(path):
                    discovered[path.relative_to(runtime.root_path).as_posix()] = path

            with SessionLocal() as db:
                stored = {
                    media.relative_path: media
                    for media in db.scalars(
                        select(MediaFile).where(MediaFile.library_id == library_id)
                    )
                }
                for relative, path in discovered.items():
                    existing = stored.get(relative)
                    try:
                        stat = path.stat()
                    except OSError:
                        continue
                    if (
                        existing is None
                        or existing.size_bytes != stat.st_size
                        or existing.mtime_ns != stat.st_mtime_ns
                    ):
                        self._queue_pending(runtime, path, relative, "Reconciliation detected a new or changed file")

                missing = set(stored) - set(discovered)
                for relative in missing:
                    self._delete_media_record(db, stored[relative])
                    self._record(
                        "removed",
                        f"Removed missing file from MediaLens metadata: {relative}",
                        runtime,
                        relative,
                    )
                if missing:
                    db.commit()

            runtime.last_reconcile_at = _utc_now()
            runtime.last_error = None if runtime.state != "error" else runtime.last_error
            self._record(
                "reconciled",
                f"Reconciled {runtime.library_name}: {len(discovered)} media files found.",
                runtime,
            )
        except Exception as exc:
            runtime.last_error = str(exc)
            runtime.state = "error" if runtime.state != "reconciliation_only" else runtime.state
            self._record("failed", f"Reconciliation failed for {runtime.library_name}: {exc}", runtime)
            logger.exception("Library reconciliation failed for %s", runtime.library_name)

    def _remove_missing_metadata(
        self,
        library_id: str,
        relative_path: str,
        runtime: LibraryRuntime,
    ) -> None:
        with SessionLocal() as db:
            media_file = db.scalar(
                select(MediaFile).where(
                    MediaFile.library_id == library_id,
                    MediaFile.relative_path == relative_path,
                )
            )
            if media_file is None:
                return
            self._delete_media_record(db, media_file)
            db.commit()
        self._record(
            "removed",
            f"Removed missing file from MediaLens metadata: {relative_path}",
            runtime,
            relative_path,
        )

    @staticmethod
    def _delete_media_record(db, media_file: MediaFile) -> None:
        item_id = media_file.media_item_id
        db.delete(media_file)
        db.flush()
        remaining = db.scalar(
            select(MediaFile.id).where(MediaFile.media_item_id == item_id).limit(1)
        )
        if remaining is None:
            item = db.get(MediaItem, item_id)
            if item is not None:
                db.delete(item)


library_watcher = LibraryWatcherManager()
