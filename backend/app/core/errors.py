from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    del request
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        payload: dict[str, Any] = {"error": exc.detail}
    else:
        payload = {
            "error": {
                "code": "HTTP_ERROR",
                "message": str(exc.detail),
                "details": {},
            }
        }
    return JSONResponse(status_code=exc.status_code, content=payload, headers=exc.headers)
