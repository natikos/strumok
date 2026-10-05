"""CsrfMiddleware coverage (#147): cookie auth is SameSite=lax, which withholds the
cookie cross-site but not from any origin the browser treats as same-site -- e.g. a
sibling tenant subdomain, if the production host isn't on the Public Suffix List. A
plain HTML form on such an origin can still submit a request that carries the cookie,
without a custom header or a CORS-preflight-triggering Content-Type. The `client`
fixture sends X-Requested-With by default (mirroring the real frontend), so tests here
that simulate the attack build a bare `TestClient` without that default header instead.
"""

from fastapi.routing import APIRoute
from pydantic import SecretStr
from starlette.testclient import TestClient

from app.core.config import settings
from app.main import app
from tests.factories import authenticate, make_user

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _bare_client(client: TestClient) -> TestClient:
    """A client sharing `client`'s cookie jar -- i.e. what a same-site attacker's
    form submission looks like -- but with none of the fixture's default headers."""
    bare = TestClient(app)
    bare.cookies.update(client.cookies)
    return bare


def _mutating_routes() -> list[tuple[str, str]]:
    """Every (method, path) pair for a non-internal route that accepts a mutating
    method, so this suite covers new routes automatically instead of needing a
    manual entry per endpoint. Static/templated paths (e.g. "/admin/households/{id}")
    are hit literally -- FastAPI's routing still matches the CSRF check before any
    path-param validation runs, since the middleware only inspects the path."""
    routes: set[tuple[str, str]] = set()
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if route.path.startswith("/internal/"):
            continue
        for method in _MUTATING_METHODS & route.methods:
            routes.add((method, route.path))
    return sorted(routes)


class TestCsrfMiddleware:
    def test_form_encoded_post_without_custom_header_is_rejected(
        self, client: TestClient
    ) -> None:
        bare = _bare_client(client)

        response = bare.post(
            "/auth/logout",
            content="",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "csrfCheckFailed"

    def test_headerless_post_simulating_plain_html_form_is_rejected(
        self, client: TestClient
    ) -> None:
        bare = _bare_client(client)

        response = bare.post("/auth/logout")

        assert response.status_code == 403
        assert response.json()["detail"] == "csrfCheckFailed"

    def test_post_with_x_requested_with_header_is_not_blocked(
        self, client: TestClient, session
    ) -> None:
        user = make_user(session)
        authenticate(client, user)

        response = client.post(
            "/auth/refresh", headers={"X-Requested-With": "XMLHttpRequest"}
        )

        assert response.status_code == 204

    def test_json_post_is_not_blocked_without_the_custom_header(
        self, client: TestClient
    ) -> None:
        bare = _bare_client(client)

        response = bare.post("/auth/logout", json={})

        assert response.status_code == 204

    def test_internal_route_is_exempt_and_works_without_the_custom_header(
        self, client: TestClient, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            settings.auth, "internal_secret", SecretStr("correct-secret")
        )
        bare = _bare_client(client)

        response = bare.post(
            "/internal/push/send-reminders",
            params={"variant": "opening"},
            headers={"X-Internal-Secret": "correct-secret"},
        )

        assert response.status_code == 200

    def test_internal_route_still_rejects_a_missing_internal_secret(
        self, client: TestClient, monkeypatch
    ) -> None:
        # The /internal/ exemption skips only the CSRF check, not authentication.
        monkeypatch.setattr(
            settings.auth, "internal_secret", SecretStr("correct-secret")
        )
        bare = _bare_client(client)

        response = bare.post(
            "/internal/push/send-reminders", params={"variant": "opening"}
        )

        assert response.status_code == 401

    def test_get_requests_are_never_blocked_regardless_of_headers(
        self, client: TestClient
    ) -> None:
        bare = _bare_client(client)

        response = bare.get("/health")

        assert response.status_code == 200

    def test_every_mutating_route_rejects_a_simple_form_request(
        self, client: TestClient
    ) -> None:
        # Covers "or any admin mutation" from the issue's acceptance criteria by
        # sweeping every mutating, non-internal route instead of naming one. The
        # CSRF check runs ahead of routing and only looks at method + path, so a
        # templated path like "/admin/households/{id}" doesn't need a real id
        # substituted to reach it.
        bare = _bare_client(client)
        routes = _mutating_routes()
        assert routes, "expected at least one mutating route to check"

        for method, path in routes:
            response = bare.request(
                method, path, content="ignored", headers={"Content-Type": "text/plain"}
            )
            assert response.status_code == 403, f"{method} {path}"
            assert response.json()["detail"] == "csrfCheckFailed", f"{method} {path}"

    def test_multipart_form_post_without_custom_header_is_rejected(
        self, client: TestClient
    ) -> None:
        bare = _bare_client(client)

        response = bare.post("/auth/logout", files={"field": (None, "value")})

        assert response.status_code == 403
        assert response.json()["detail"] == "csrfCheckFailed"
