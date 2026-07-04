"""
Core Email sending service using aiosmtplib (async SMTP).
Production features:
- Proper MIME construction (text + html + attachments)
- STARTTLS / SSL support
- Message-ID generation
- Comprehensive error handling & logging
- Support for custom headers and sender override
"""

import aiosmtplib
from aiosmtplib import SMTPException, SMTPConnectError, SMTPAuthenticationError
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
import base64
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.config import settings
from app.schemas.email import SendEmailRequest, SendEmailResponse, AttachmentSchema

logger = logging.getLogger(__name__)


def _get_all_recipients(req: SendEmailRequest) -> List[str]:
    """Collect all recipients for SMTP envelope (To + CC + BCC)."""
    recipients = []
    recipients.extend([str(email) for email in req.recipients.to])
    if req.recipients.cc:
        recipients.extend([str(email) for email in req.recipients.cc])
    if req.recipients.bcc:
        recipients.extend([str(email) for email in req.recipients.bcc])
    return list(set(recipients))  # dedupe just in case


def _build_email_message(req: SendEmailRequest):
    """Construct a proper MIME EmailMessage supporting text/html + attachments.
    Returns tuple: (EmailMessage, message_id)
    """
    msg = EmailMessage()

    # Headers
    from_email = str(req.sender) if req.sender else str(settings.smtp_from_email)
    from_name = settings.smtp_from_name
    msg["From"] = formataddr((from_name, from_email))

    msg["To"] = ", ".join([str(e) for e in req.recipients.to])
    if req.recipients.cc:
        msg["Cc"] = ", ".join([str(e) for e in req.recipients.cc])
    # BCC is intentionally NOT added to headers (only envelope recipients)

    msg["Subject"] = req.subject
    msg["Date"] = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
    msg["X-Mailer"] = f"{settings.app_name} v1.0"

    if req.reply_to:
        msg["Reply-To"] = str(req.reply_to)
    elif settings.default_reply_to:
        msg["Reply-To"] = str(settings.default_reply_to)

    # Custom headers (e.g. for ESP tracking, campaign IDs)
    if req.headers:
        for key, value in req.headers.items():
            # Prevent override of critical headers
            if key.lower() not in ["from", "to", "cc", "bcc", "subject", "date", "message-id"]:
                msg[key] = str(value)[:500]  # safety limit

    # Generate unique Message-ID
    domain = from_email.split("@")[-1] if "@" in from_email else "localhost"
    message_id = make_msgid(domain=domain)
    msg["Message-ID"] = message_id

    # Body content
    if req.text_body and req.html_body:
        msg.set_content(req.text_body)
        msg.add_alternative(req.html_body, subtype="html")
    elif req.html_body:
        msg.set_content(req.html_body, subtype="html")
    elif req.text_body:
        msg.set_content(req.text_body)
    else:
        msg.set_content("[No body content provided]")

    # Attachments
    if req.attachments:
        for att in req.attachments:
            try:
                content_bytes = base64.b64decode(att.content_base64)
                # Split MIME type
                if "/" in att.content_type:
                    maintype, subtype = att.content_type.split("/", 1)
                else:
                    maintype, subtype = "application", "octet-stream"

                msg.add_attachment(
                    content_bytes,
                    maintype=maintype,
                    subtype=subtype,
                    filename=att.filename
                )
                logger.debug(f"Attached file: {att.filename} ({len(content_bytes)} bytes)")
            except Exception as e:
                logger.error(f"Failed to attach {att.filename}: {e}")
                # Continue with other attachments; do not fail whole email

    return msg, message_id


async def send_email(req: SendEmailRequest) -> SendEmailResponse:
    """
    Send email via SMTP using aiosmtplib.
    This function is designed to be called from BackgroundTasks or a task queue.
    """
    message_id = None
    try:
        msg, message_id = _build_email_message(req)
        all_recipients = _get_all_recipients(req)

        if not all_recipients:
            raise ValueError("No recipients specified")

        logger.info(
            f"Sending email | subject='{req.subject}' | to={len(req.recipients.to)} | "
            f"cc={len(req.recipients.cc or [])} | bcc={len(req.recipients.bcc or [])} | "
            f"attachments={len(req.attachments or [])} | message_id={message_id}"
        )

        # Create SMTP client
        smtp = aiosmtplib.SMTP(
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            timeout=30,  # seconds
            use_tls=settings.smtp_use_ssl,  # Implicit TLS (usually port 465)
        )

        async with smtp:
            # STARTTLS for ports like 587 (if not using implicit SSL)
            if not settings.smtp_use_ssl and settings.smtp_use_tls:
                await smtp.starttls()
                logger.debug("STARTTLS negotiated successfully")

            # Authenticate
            if settings.smtp_user and settings.smtp_password:
                await smtp.login(settings.smtp_user, settings.smtp_password)
                logger.debug("SMTP authentication successful")

            # Send the message
            # send_message handles envelope recipients (incl. BCC) correctly
            # It raises on hard errors; on success returns the server response string
            response = await smtp.send_message(
                msg,
                sender=str(req.sender) if req.sender else str(settings.smtp_from_email),
                recipients=all_recipients
            )

            logger.info(f"Email sent successfully | message_id={message_id} | smtp_response={response}")

            return SendEmailResponse(
                success=True,
                message="Email accepted for delivery by SMTP server",
                message_id=message_id,
                status="sent"
            )

    except SMTPAuthenticationError as e:
        logger.error(f"SMTP Authentication failed: {e}")
        return SendEmailResponse(
            success=False,
            message="SMTP authentication failed. Check credentials.",
            message_id=message_id,
            status="failed",
            error=str(e) if settings.debug else "Authentication error"
        )
    except SMTPConnectError as e:
        logger.error(f"SMTP Connection failed to {settings.smtp_host}:{settings.smtp_port}: {e}")
        return SendEmailResponse(
            success=False,
            message="Failed to connect to SMTP server",
            message_id=message_id,
            status="failed",
            error=str(e) if settings.debug else "Connection error"
        )
    except SMTPException as e:
        logger.error(f"SMTP error occurred: {e}")
        return SendEmailResponse(
            success=False,
            message="SMTP protocol error during send",
            message_id=message_id,
            status="failed",
            error=str(e) if settings.debug else "SMTP error"
        )
    except Exception as e:
        logger.exception(f"Unexpected error sending email: {e}")
        return SendEmailResponse(
            success=False,
            message="Internal error while sending email",
            message_id=message_id,
            status="failed",
            error=str(e) if settings.debug else "Internal server error"
        )