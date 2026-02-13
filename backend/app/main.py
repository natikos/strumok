from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.core.config import settings
from app.db.engine import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield
    # Perform any necessary cleanup here if needed


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(auth_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        port=settings.app_port,
        reload=settings.environment == "development",
    )
