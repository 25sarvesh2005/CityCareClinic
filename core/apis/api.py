"""
Master API Router mounting all domain sub-routers under /api.
Individual sub-routers define explicit version paths (e.g. /v1/...).
"""

from fastapi import APIRouter

from chatbot.routes.chat_routes import router as chat_router
from core.apis.routes.admin_routes import router as admin_router
from core.apis.routes.appointment_routes import router as appointment_router
from core.apis.routes.auth_routes import router as auth_router
from core.apis.routes.doctor_routes import router as doctor_router
from core.apis.routes.hospital_routes import router as hospital_router
from core.apis.routes.prescription_routes import router as prescription_router

api_router = APIRouter(prefix="/api")

# Include domain-specific modular routers with /v1 versioned endpoint paths
api_router.include_router(auth_router)
api_router.include_router(appointment_router)
api_router.include_router(doctor_router)
api_router.include_router(admin_router)
api_router.include_router(hospital_router)
api_router.include_router(prescription_router)
api_router.include_router(chat_router)
