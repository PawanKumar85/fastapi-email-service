"""
FastAPI Email Microservice - Production Grade
Entry point for the application.

Features:
- Async SMTP via aiosmtplib
- Pydantic validation + EmailStr
- API Key authentication
- Background task processing
- Structured logging
- CORS, health checks, OpenAPI docs
- Environment driven configuration
"""

import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.routers.email_router import router as email_router

# Configure logging (production friendly JSON-ish format)
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("email-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown events."""
    logger.info(f"🚀 Starting {settings.app_name}")
    logger.info(f"SMTP: {settings.smtp_host}:{settings.smtp_port} (TLS={settings.smtp_use_tls}, SSL={settings.smtp_use_ssl})")
    logger.info(f"From: {settings.smtp_from_email}")
    logger.info(f"Debug mode: {settings.debug}")
    if settings.debug:
        logger.warning("⚠️  Running in DEBUG mode - do not use in production!")
    yield
    logger.info("👋 Shutting down Email Service gracefully")


app = FastAPI(
    title=settings.app_name,
    description="""
    **Production-grade Email Microservice** built with FastAPI + aiosmtplib.
    
    ### Features
    - Send emails with plain text + HTML (multipart)
    - Attachments (base64, up to 5 files)
    - CC / BCC support
    - Custom headers, Reply-To, sender override
    - Secure API Key authentication (X-API-Key header)
    - Background processing (non-blocking)
    - Full OpenAPI / Swagger docs at `/docs`
    - Health & config endpoints
    
    ### Authentication
    All protected routes require header: `X-API-Key: <your-api-key>`
    
    ### Production Recommendations
    - Use a proper task queue (Celery + Redis/RabbitMQ) for very high volume
    - Add retry logic with exponential backoff (tenacity)
    - Monitor SMTP bounce/complaint webhooks from your ESP
    - Set up structured logging + tracing (OpenTelemetry)
    - Use secrets manager (AWS Secrets, Vault) instead of .env in prod
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS Middleware (configure origins in .env)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# Exception handlers for nice error responses
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail if isinstance(exc.detail, str) else "HTTP error",
            "status": "error",
            "path": str(request.url.path),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "Validation error in request body",
            "status": "validation_error",
            "errors": exc.errors(),
            "path": str(request.url.path),
        },
    )


# Include routers
app.include_router(email_router)


@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint - redirect info."""
    return {
        "service": settings.app_name,
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/emails/health",
        "message": "Production Email Service ready. See /docs for API reference."
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )