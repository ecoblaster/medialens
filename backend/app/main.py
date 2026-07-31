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

        # Upgrade existing databases immediately, including files that are
        # unchanged and would otherwise be skipped by the next scanner pass.
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
brands_dir = frontend_dir / "brands"

if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
if brands_dir.exists():
    app.mount("/brands", StaticFiles(directory=brands_dir), name="brands")


@app.get("/", include_in_schema=False)
def root():
    index = frontend_dir / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"name": settings.app_name, "version": settings.app_version, "docs": "/docs"}


@app.get("/favicon.svg", include_in_schema=False)
def favicon_svg():
    favicon = frontend_dir / "favicon.svg"
    if favicon.exists():
        return FileResponse(favicon, media_type="image/svg+xml")
    raise HTTPException(status_code=404, detail="Favicon not found")


@app.get("/{full_path:path}", include_in_schema=False)
def frontend_fallback(full_path: str):
    if full_path.startswith(("api/", "docs", "openapi.json", "redoc")):
        raise HTTPException(status_code=404, detail="Not found")
    public_file = (frontend_dir / full_path).resolve()
    if public_file.is_relative_to(frontend_dir) and public_file.is_file():
        return FileResponse(public_file)
    index = frontend_dir / "index.html"
    if index.exists():
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Frontend is not built")
