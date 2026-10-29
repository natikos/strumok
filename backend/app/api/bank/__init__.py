from fastapi import APIRouter

from app.api.bank.routes import review_router
from app.api.bank.routes import router as upload_router

router = APIRouter()
router.include_router(upload_router)
router.include_router(review_router)

__all__ = ["router"]
