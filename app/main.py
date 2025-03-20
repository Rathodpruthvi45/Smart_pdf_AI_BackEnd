from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import os
from pathlib import Path

from .core.config import settings
from .db.database import engine, Base
from .core.rate_limiter import setup_rate_limiter
from .api import auth, users, protected
from .api.endpoints import smart_AI_pdf


# Create the database tables
Base.metadata.create_all(bind=engine)

# Create the FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Add request ID middleware
@app.middleware("http")
async def add_request_id_middleware(request: Request, call_next):
    """
    Add a request ID to the response headers
    """
    request_id = request.headers.get("X-Request-ID", str(time.time()))
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# Add process time middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """
    Add the processing time to the response headers
    """
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Add security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """
    Add security headers to the response
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response


# Add routers
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(users.router, prefix=settings.API_V1_STR)
app.include_router(protected.router, prefix=settings.API_V1_STR)
app.include_router(smart_AI_pdf.router, prefix=settings.API_V1_STR)



@app.on_event("startup")
async def startup_event():
    """
    Initialize services on startup
    """
    # Create templates directory if it doesn't exist
    templates_path = Path(__file__).parent / "templates"
    if not templates_path.exists():
        os.makedirs(templates_path)

    # Create email templates directory if it doesn't exist
    email_templates_path = templates_path / "email"
    if not email_templates_path.exists():
        os.makedirs(email_templates_path)


@app.get("/")
async def root():
    """
    Root endpoint
    """
    return {"message": "Welcome to the Auth API", "docs": "/docs", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    return {"status": "ok", "timestamp": time.time()}
