from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.meter_readings import router as meter_readings_router

__all__ = ["admin_router", "auth_router", "meter_readings_router"]
