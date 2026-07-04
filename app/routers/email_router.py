"""
FastAPI router for Email endpoints.
Includes API Key authentication and BackgroundTasks for non-blocking sends.
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Header
from fastapi.security import APIKeyHeader
from typing import Optional
import logging

from app.config import settings
from app.schemas.email import SendEmailRequest, SendEmailResponse, HealthResponse
from app.services.email_service import send_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/emails", tags=["Emails"])

# API Key security scheme (used in Swagger UI as well)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


async def verify_api_key(api_key: str = Depends(api_key_header)):
    """Dependency to validate API key from header."""
    if api_key != settings.api_key:
        logger.warning("Invalid API key attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key


@router.post(
    "/send",
    response_model=SendEmailResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send an email via SMTP",
    description="""
    Send a transactional or marketing email using configured SMTP server.
    
    - Supports plain text + HTML (multipart/alternative)
    - Attachments via base64 (max 5 files, 10MB each)
    - CC, BCC, custom Reply-To, sender override, custom headers
    - Returns 202 Accepted immediately (email processed in background)
    - Use X-API-Key header for authentication
    """,
    responses={
        202: {"description": "Email accepted for background processing"},
        400: {"description": "Validation error (bad request body)"},
        401: {"description": "Invalid or missing X-API-Key"},
        500: {"description": "Internal server error (check logs)"},
    },
)
async def send_email_endpoint(
    email_data: SendEmailRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key),
) -> SendEmailResponse:
    """
    Accepts email request and queues it for background sending.
    This prevents blocking the API worker during SMTP I/O.
    """
    # Optional: Add tags to request for logging context
    if email_data.tags:
        logger.info(f"Email request received with tags: {email_data.tags}")

    # Add the send task to background
    background_tasks.add_task(send_email_task, email_data)

    # Return immediately
    return SendEmailResponse(
        success=True,
        message="Email request accepted and queued for delivery",
        status="accepted",
        message_id=None,  # Will be generated during actual send
    )


async def send_email_task(email_data: SendEmailRequest):
    """Background task wrapper (can be replaced with Celery/Redis in high-scale prod)."""
    try:
        result = await send_email(email_data)
        if result.success:
            logger.info(f"Background send completed successfully: {result.message_id}")
        else:
            logger.error(f"Background send failed: {result.message} | error={result.error}")
    except Exception as e:
        logger.exception(f"Critical error in background email task: {e}")


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check endpoint",
    description="Check if the email service and SMTP config are reachable (basic check, no actual send).",
)
async def health_check():
    """Simple health check. For production, add SMTP connectivity test if needed."""
    return HealthResponse(
        status="healthy",
        service=settings.app_name,
        smtp_configured=bool(settings.smtp_host and settings.smtp_from_email),
        debug=settings.debug,
    )


@router.get(
    "/config",
    summary="Public configuration (non-sensitive)",
    description="Returns non-sensitive service configuration. Useful for debugging and monitoring.",
    dependencies=[Depends(verify_api_key)],
)
async def get_config():
    """Protected endpoint returning safe config info."""
    from app.config import get_public_settings
    return get_public_settings()