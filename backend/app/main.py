from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.api.router import api_router
from app.core.config import settings
from app.core.errors import http_exception_handler
from app.db.base import utc_now
from app.db.session import SessionLocal
from app.models.enums import ScanRunStatus
from app.models.library import Library
from app.models.scan import ScanRun
import app.services.library_watcher as library_watcher_module
from app.services.library_watcher import library_watcher
from app.services.media_paths import is_supported_media_path
from app.services.media_versions import synchronize_library_versions


@asynccontextmanager
async def lifespan(_: FastAPI):
    # BackgroundTasks live only inside the running API process. Any scan left
    # active after a container restart has lost its worker and must be closed.
    with SessionLocal() as db:
        orphaned = list(
            db.scalars(
                select(ScanRun).where(
                    ScanRun.status.in_(
                        [
                            ScanRunStatus.QUEUED.value,
                            ScanRunStatus.RUNNING.value,
                            ScanRunStatus.CANCELLING.value,
                        ]
                    )
                )
            )
        )
        for scan in orphaned:
            scan.status = ScanRunStatus.CANCELLED.value
            scan.completed_at = utc_now()
            scan.error_message = "Scan was cancelled because the MediaLens service restarted."
        if orphaned:
            db.commit()

        # Existing installations may already contain one MediaItem per physical
        # file. Reconcile them once at startup so upgrading immediately exposes
        # 1080p, 4K, remux, and HDR variants under the same title without a
        # destructive migration or forced media probe.
        library_ids = list(db.scalars(select(Library.id)).all())
        for library_id in library_ids:
            synchronize_library_versions(db, library_id)
        if library_ids:
            db.commit()

    # Keep the existing watcher implementation isolated while installing the
    # central media-path policy used by automatic events and reconciliation.
    # Reconciliation will also remove previously stored sample/promo entries.
    library_watcher_module._is_supported = is_supported_media_path
    library_watcher.start()
    try:
        yield
    finally:
        library_watcher.stop()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Read-only media library capability analyzer.",
    lifespan=lifespan,
)

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_v1_prefix)

frontend_dir = Path("/app/frontend")
assets_dir = frontend_dir / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

brands_dir = frontend_dir / "brands"
if brands_dir.exists():
    app.mount("/brands", StaticFiles(directory=brands_dir), name="frontend-brands")

favicon_path = frontend_dir / "favicon.png"


@app.get("/favicon.png", include_in_schema=False)
def favicon() -> FileResponse:
    if favicon_path.exists():
        return FileResponse(favicon_path)
    raise HTTPException(status_code=404, detail="Favicon is not built")


@app.get("/{full_path:path}", include_in_schema=False)
def frontend(full_path: str) -> FileResponse:
    requested = frontend_dir / full_path
    if full_path and requested.is_file():
        return FileResponse(requested)
    index = frontend_dir / "index.html"
    if index.exists():
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Frontend is not built")
