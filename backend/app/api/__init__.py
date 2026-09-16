from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.electricity_rates.routes import router as electricity_rates_router
from app.api.meter_readings import router as meter_readings_router

__all__ = [
    "admin_router",
    "auth_router",
    "electricity_rates_router",
    "meter_readings_router",
]
