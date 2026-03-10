import os
import smtplib
from email.message import EmailMessage

import resend
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


router = APIRouter(tags=["Support Contact"])


class ContactFormRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: str = Field(..., min_length=5, max_length=255)
    subject: str = Field(..., min_length=3, max_length=200)
    # No length limits for message (user can send any amount)
    message: str


def _require_smtp_config() -> dict:
    host = os.getenv("SMTP_HOST")
    port = os.getenv("SMTP_PORT")
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("SMTP_FROM_EMAIL", username or "")
    recipient = os.getenv("SUPPORT_CONTACT_RECIPIENT", "kevin@founderport.ai")
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes"}

    if not host or not port or not username or not password or not from_email:
        raise HTTPException(
            status_code=500,
            detail=(
                "Email server is not configured. Missing one or more of: "
                "SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM_EMAIL."
            ),
        )

    try:
        parsed_port = int(port)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="SMTP_PORT must be a valid integer.") from exc

    return {
        "host": host,
        "port": parsed_port,
        "username": username,
        "password": password,
        "from_email": from_email,
        "recipient": recipient,
        "use_tls": use_tls,
    }


def _send_contact_email(payload: ContactFormRequest) -> None:
    api_key = os.getenv("RESEND_API_KEY")
    recipient = os.getenv("SUPPORT_CONTACT_RECIPIENT", "kevin@founderport.ai")
    from_email = os.getenv("SMTP_FROM_EMAIL", "support@founderport.ai")
    from_name = os.getenv("SMTP_FROM_NAME", "Founderport")

    body = "\n".join(
        [
            "New Contact Us submission:",
            "",
            f"Name: {payload.name}",
            f"Email: {payload.email}",
            f"Subject: {payload.subject}",
            "",
            "Message:",
            payload.message,
        ]
    )

    if api_key:
        try:
            resend.api_key = api_key
            resend.Emails.send({
                "from": f"{from_name} <{from_email}>",
                "to": [recipient],
                "subject": f"[Founderport Contact] {payload.subject}",
                "text": body,
            })
        except Exception as exc:
            raise HTTPException(status_code=500, detail="Failed to send contact email.") from exc
    else:
        cfg = _require_smtp_config()
        msg = EmailMessage()
        msg["Subject"] = f"[Founderport Contact] {payload.subject}"
        msg["From"] = cfg["from_email"]
        msg["To"] = recipient
        msg.set_content(body)
        try:
            if cfg["use_tls"]:
                with smtplib.SMTP(cfg["host"], cfg["port"], timeout=20) as server:
                    server.starttls()
                    server.login(cfg["username"], cfg["password"])
                    server.send_message(msg)
            else:
                with smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=20) as server:
                    server.login(cfg["username"], cfg["password"])
                    server.send_message(msg)
        except Exception as exc:
            raise HTTPException(status_code=500, detail="Failed to send contact email.") from exc


@router.post("/contact")
async def submit_contact_form(payload: ContactFormRequest):
    _send_contact_email(payload)
    return {"success": True, "message": "Your message has been sent successfully."}

