from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _is_allowed(request: Request) -> bool:
    """Allow only requests a plain HTML form can't produce: an X-Requested-With
    header or a JSON content type. Both force a CORS preflight, which blocks
    untrusted origins. Relies on CORS_ORIGINS never containing "*"."""
    if "x-requested-with" in request.headers:
        return True

    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    return content_type == "application/json"


class CsrfMiddleware(BaseHTTPMiddleware):
    """Cookie auth is SameSite=lax: it withholds the cookie on a cross-site request,
    but any origin the browser considers same-site -- e.g. a sibling tenant
    subdomain, if the production host isn't on the Public Suffix List -- can still
    submit a plain HTML form that carries it. A body-less mutating endpoint (logout,
    refresh) or one that doesn't otherwise validate its form-encoded body is
    triggerable that way unless every mutation requires something a form can't send.
    See issue #147."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        if request.method not in _MUTATING_METHODS:
            return await call_next(request)

        if not _is_allowed(request):
            return JSONResponse(status_code=403, content={"detail": "csrfCheckFailed"})

        return await call_next(request)
