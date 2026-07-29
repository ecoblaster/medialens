from fastapi import APIRouter

from app.api.routes import compatibility, dashboard, files, health, libraries, scans, watcher

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(libraries.router)
api_router.include_router(scans.router)
api_router.include_router(files.router)
api_router.include_router(dashboard.router)
api_router.include_router(compatibility.router)
api_router.include_router(watcher.router)
