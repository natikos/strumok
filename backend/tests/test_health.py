from app.db import engine as engine_module
from app.main import app
from sqlmodel import create_engine
from starlette.testclient import TestClient


def test_health_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_503_when_db_unreachable(monkeypatch):
    monkeypatch.setattr(
        engine_module,
        "probe_engine",
        create_engine(
            "postgresql+psycopg://x:x@127.0.0.1:1/x",
            connect_args={"connect_timeout": 1},
        ),
    )
    response = TestClient(app).get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "db": "unreachable"}
