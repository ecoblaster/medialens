from typing import Literal

from pydantic import BaseModel


class ScannerTools(BaseModel):
    ffprobe: bool
    mediainfo: bool
    dovi_tool: bool


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "error"]
    scanner_tools: ScannerTools
