from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.api.bank.service import MAX_BYTES

UPLOAD_PATH = "/admin/bank-statements"
# Multipart framing around the file part.
_OVERHEAD = 16 * 1024


class UploadSizeMiddleware(BaseHTTPMiddleware):
    """Multipart bodies are parsed (and spooled to temp disk past 1 MB) before
    any dependency, including auth, runs. Refusing on Content-Length first keeps
    an oversized or unauthenticated upload from ever being received."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        if request.method == "POST" and request.url.path.rstrip("/") == UPLOAD_PATH:
            try:
                length = int(request.headers.get("content-length", ""))
            except ValueError:
                length = None
            if length is None or length > MAX_BYTES + _OVERHEAD:
                return JSONResponse(
                    status_code=413, content={"detail": "bankStatementTooLarge"}
                )
        return await call_next(request)
