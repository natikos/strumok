from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# Every route under this prefix authenticates via X-Internal-Secret instead of the
# cookie (see require_internal_secret), so it can't be ridden by a forged same-site
# form submission. Any new router mounted here must keep that guarantee.
_EXEMPT_PATH_PREFIXES = ("/internal/",)


def _is_allowed(request: Request) -> bool:
    """Allowlist, not denylist: a request is let through only if it's one an HTML
    form, sendBeacon(), or a no-cors fetch() cannot produce on its own -- i.e. one
    that forces the browser to run a CORS preflight first. That's exactly
    application/json, or any custom header such as X-Requested-With. Everything a
    plain cross-origin (or, since cookies here are SameSite=lax, same-site)
    attacker's form can send is rejected."""
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

        if request.url.path.startswith(_EXEMPT_PATH_PREFIXES):
            return await call_next(request)

        if not _is_allowed(request):
            return JSONResponse(status_code=403, content={"detail": "csrfCheckFailed"})

        return await call_next(request)
