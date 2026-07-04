"""
Pydantic schemas for Email Service API.
Request/Response models with validation.
"""

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from typing import List, Optional, Dict, Any
import base64


class AttachmentSchema(BaseModel):
    """Attachment for email (base64 encoded content for JSON API)."""
    filename: str = Field(..., min_length=1, max_length=255, description="Name of the file including extension")
    content_base64: str = Field(..., description="Base64 encoded file content")
    content_type: str = Field(
        default="application/octet-stream",
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9!#$&^_.-]{0,126}/[a-zA-Z0-9][a-zA-Z0-9!#$&^_.-]{0,126}$",
        description="MIME type e.g. application/pdf, image/png"
    )

    @field_validator("content_base64")
    @classmethod
    def validate_base64(cls, v: str) -> str:
        """Ensure content is valid base64 and not too large (e.g. < 10MB decoded)."""
        try:
            decoded = base64.b64decode(v, validate=True)
            if len(decoded) > 10 * 1024 * 1024:  # 10 MB limit
                raise ValueError("Attachment too large (>10MB). Consider using object storage + link instead.")
            return v
        except Exception as e:
            raise ValueError(f"Invalid base64 content: {str(e)}")


class RecipientsSchema(BaseModel):
    """Email recipients."""
    to: List[EmailStr] = Field(..., min_length=1, max_items=50, description="Primary recipients (max 50)")
    cc: Optional[List[EmailStr]] = Field(default_factory=list, max_items=20)
    bcc: Optional[List[EmailStr]] = Field(default_factory=list, max_items=20)


class SendEmailRequest(BaseModel):
    """Request body for sending an email."""
    recipients: RecipientsSchema = Field(..., description="To, CC, BCC recipients")
    subject: str = Field(..., min_length=1, max_length=200, description="Email subject line")
    text_body: Optional[str] = Field(
        default=None,
        max_length=50000,
        description="Plain text body (required if no html_body)"
    )
    html_body: Optional[str] = Field(
        default=None,
        max_length=100000,
        description="HTML body (optional, enables multipart/alternative)"
    )
    sender: Optional[EmailStr] = Field(
        default=None,
        description="Override the default From address (must be authorized in your SMTP provider)"
    )
    reply_to: Optional[EmailStr] = Field(default=None, description="Reply-To address")
    attachments: Optional[List[AttachmentSchema]] = Field(
        default=None,
        max_length=5,
        description="List of attachments (max 5 files, each <10MB)"
    )
    headers: Optional[Dict[str, str]] = Field(
        default=None,
        description="Custom headers e.g. {'X-Campaign-ID': 'summer-2026'}"
    )
    tags: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Metadata tags for logging/tracking (not sent in email)"
    )

    @model_validator(mode="after")
    def validate_at_least_one_body(self):
        if not self.text_body and not self.html_body:
            raise ValueError("Either text_body or html_body (or both) must be provided")
        return self

    model_config = {
        "json_schema_extra": {
            "example": {
                "recipients": {
                    "to": ["user@example.com", "another@domain.com"],
                    "cc": ["cc@example.com"],
                    "bcc": []
                },
                "subject": "Welcome to Our Platform",
                "text_body": "Hello! Thanks for signing up.",
                "html_body": "<h1>Welcome!</h1><p>Thanks for signing up.</p>",
                "sender": "noreply@yourcompany.com",
                "reply_to": "support@yourcompany.com",
                "attachments": [
                    {
                        "filename": "welcome-guide.pdf",
                        "content_base64": "JVBERi0xLjQKJcOkw7zDtsOfCjIgMCBvYmoKPDwvTGVuZ3RoIDMgMCBSL0ZpbHRlci9GbGF0ZURlY29kZT4+CnN0cmVhbQp4nDPUM1Qw...",
                        "content_type": "application/pdf"
                    }
                ],
                "headers": {"X-User-ID": "12345"},
                "tags": {"campaign": "onboarding", "user_id": 42}
            }
        }
    }


class SendEmailResponse(BaseModel):
    """Response after attempting to send email."""
    success: bool = Field(..., description="Whether the email was accepted for delivery")
    message: str = Field(..., description="Human readable status message")
    message_id: Optional[str] = Field(
        default=None,
        description="Unique Message-ID generated for the email (useful for tracking with provider)"
    )
    status: str = Field(
        default="accepted",
        description="Delivery status: accepted, sent, failed"
    )
    error: Optional[str] = Field(default=None, description="Error details if failed (only in debug/non-prod)")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    service: str
    version: str = "1.0.0"
    smtp_configured: bool
    debug: bool