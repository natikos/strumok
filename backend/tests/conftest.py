"""Test harness: throwaway Postgres database + per-test savepoint rollback.

Import order matters here. ``app.core.config`` builds its ``settings`` singleton at
import time and ``app.db.engine`` builds the engine from it, so the test database
URL has to be in ``os.environ`` *before* anything under ``app.`` is imported. That
is why the environment setup below runs at module top level rather than in a
fixture, and why the ``app`` imports sit underneath it.
"""

import os
import uuid
from urllib.parse import urlsplit, urlunsplit

import pytest

# --- Environment must be configured before importing anything from `app`. ------

ADMIN_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/postgres"
)

LOCAL_HOSTNAMES = {"localhost", "127.0.0.1", "::1", "postgres"}


def _assert_local(url: str) -> None:
    """Refuse to run against a non-local database.

    ``backend/.env`` holds real development credentials and pydantic-settings reads
    it automatically, so without this guard a misconfigured run would happily
    create and drop tables in a database someone cares about.
    """
    hostname = urlsplit(url).hostname
    if hostname not in LOCAL_HOSTNAMES:
        raise RuntimeError(
            f"Refusing to run tests against non-local database host {hostname!r}. "
            "Point TEST_DATABASE_URL at a local Postgres instance."
        )


_assert_local(ADMIN_DATABASE_URL)

# A unique database per run keeps concurrent runs (and a crashed previous run)
# from colliding.
TEST_DB_NAME = f"strumok_test_{uuid.uuid4().hex[:12]}"

_parts = urlsplit(ADMIN_DATABASE_URL)
TEST_DATABASE_URL = urlunsplit(_parts._replace(path=f"/{TEST_DB_NAME}"))

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["AUTH_SECRET_KEY"] = "test-secret-key-not-used-anywhere-real"
# Must stay "development": `settings.auth_cookie_secure` is `environment !=
# "development"`, and a Secure cookie is never sent back over the test client's
# plain-http transport, so any other value breaks every authenticated request.
os.environ["ENVIRONMENT"] = "development"

# --- Now safe to import the application. --------------------------------------

from sqlalchemy import event, text  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402
from sqlmodel import Session, SQLModel, create_engine  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db import engine as engine_module  # noqa: E402
from app.main import app  # noqa: E402


def _admin_engine() -> Engine:
    """Engine against the maintenance database, for CREATE/DROP DATABASE."""
    return create_engine(ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")


@pytest.fixture(scope="session", autouse=True)
def _database() -> object:
    """Create the throwaway database for the whole session, then drop it."""
    if settings.db.url != TEST_DATABASE_URL:
        raise RuntimeError(
            "Application settings did not pick up the test database URL "
            f"(got {settings.db.url!r}). Check conftest import order."
        )

    admin = _admin_engine()
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}"'))
        conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))

    try:
        yield
    finally:
        engine_module.engine.dispose()
        with admin.connect() as conn:
            # Evict anything still attached, or DROP DATABASE blocks.
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :name AND pid <> pg_backend_pid()"
                ),
                {"name": TEST_DB_NAME},
            )
            conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}"'))
        admin.dispose()


@pytest.fixture(scope="session")
def engine(_database: object) -> object:
    """The application's own engine, with the schema created once per session."""
    SQLModel.metadata.create_all(engine_module.engine)
    return engine_module.engine


@pytest.fixture
def session(engine) -> object:
    """A session whose writes are always rolled back.

    ``submit_meter_reading`` calls ``session.commit()`` itself (and
    ``session.rollback()`` when the unique constraint fires), which would end a
    plain outer transaction and let rows escape. So the session is bound to an
    external transaction and started in "joined" mode: the service's ``commit()``
    releases a SAVEPOINT rather than the real transaction, and the listener below
    opens a fresh SAVEPOINT so the session stays usable afterwards. The outer
    transaction is then rolled back wholesale at teardown.
    """
    connection = engine.connect()
    transaction = connection.begin()
    test_session = Session(bind=connection, join_transaction_mode="create_savepoint")

    @event.listens_for(test_session, "after_transaction_end")
    def _restart_savepoint(sess: Session, trans: object) -> None:
        # Re-open a nested transaction whenever the service commits/rolls back its
        # own, so subsequent statements in the same test still have one.
        if trans.nested and not trans._parent.nested:  # type: ignore[attr-defined]
            if sess.is_active:
                sess.begin_nested()

    try:
        yield test_session
    finally:
        event.remove(test_session, "after_transaction_end", _restart_savepoint)
        test_session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.fixture
def client(session: Session) -> object:
    """TestClient wired to the rolled-back session.

    Only ``get_session`` is overridden. Authentication is deliberately left real —
    tests log in over HTTP and carry the cookie — because household scoping is the
    boundary most worth testing and stubbing ``get_current_user`` would mock away
    the very thing under test.
    """

    def _override_get_session():
        yield session

    # `app.api.deps.auth` imports get_session from `app.db.engine` while the routes
    # import it from `app.db`; both re-export the same function object, so a single
    # override by identity covers both call sites.
    app.dependency_overrides[engine_module.get_session] = _override_get_session
    try:
        # No context manager: entering it would run the lifespan, whose init_db()
        # create_all would commit DDL outside our rolled-back transaction.
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
