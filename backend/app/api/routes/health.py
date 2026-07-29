import shutil

from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import engine
from app.schemas.health import HealthResponse, ScannerTools

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    database_status = "ok"
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        database_status = "error"

    tools = ScannerTools(
        ffprobe=shutil.which("ffprobe") is not None,
        mediainfo=shutil.which("mediainfo") is not None,
        dovi_tool=shutil.which("dovi_tool") is not None,
    )

    return HealthResponse(
        status="ok" if database_status == "ok" else "degraded",
        database=database_status,
        scanner_tools=tools,
    )
