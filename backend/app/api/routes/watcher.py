from fastapi import APIRouter

from app.schemas.watcher import WatcherCommandRead, WatcherStatusRead
from app.services.library_watcher import library_watcher

router = APIRouter(prefix="/watcher", tags=["automatic scanning"])


@router.get("/status", response_model=WatcherStatusRead)
def watcher_status() -> WatcherStatusRead:
    return library_watcher.status()


@router.post("/reconcile", response_model=WatcherCommandRead)
def reconcile_now() -> WatcherCommandRead:
    status = library_watcher.status()
    if not status.enabled:
        return WatcherCommandRead(
            accepted=False,
            message="Automatic scanning is disabled by configuration.",
        )
    library_watcher.refresh_libraries()
    return WatcherCommandRead(
        accepted=True,
        message="Library reconciliation completed and changed files were queued.",
    )
