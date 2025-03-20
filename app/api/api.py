from fastapi import APIRouter
from .endpoints import auth, smart_AI_pdf, admin

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(smart_AI_pdf.router, prefix="/v1", tags=["smart_AI_pdf"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
