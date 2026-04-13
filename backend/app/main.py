from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import auth_router
from app.core.config import settings
from app.db.engine import init_db

DIST_DIR = Path(__file__).resolve().parent.parent / "dist"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield
    # Perform any necessary cleanup here if needed


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)
app.include_router(auth_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# dist/ is created by the frontend build (bun run build) and won't exist during development
if DIST_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")

    @app.get("/{path:path}")
    def serve_spa(path: str):
        file = DIST_DIR / path
        if file.is_file():
            return FileResponse(file)
        return FileResponse(DIST_DIR / "index.html")


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        port=settings.app_port,
        reload=settings.environment == "development",
    )
