import logging
import os
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

RECAPTCHA_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"


async def verify_recaptcha_token(token: Optional[str], remote_ip: Optional[str] = None) -> None:
    """
    Verifies a Google reCAPTCHA token.

    Behavior:
    - If `RECAPTCHA_SECRET_KEY` is not set, verification is skipped.
    - If secret is set, `token` is required and must verify successfully.
    """
    secret_key = os.getenv("RECAPTCHA_SECRET_KEY")
    if not secret_key:
        return

    if not token:
        raise ValueError("Captcha token is required.")

    data: dict[str, Any] = {"secret": secret_key, "response": token}
    if remote_ip:
        data["remoteip"] = remote_ip

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(RECAPTCHA_VERIFY_URL, data=data)
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        logger.warning("reCAPTCHA verification request failed: %s", exc)
        raise ValueError("Captcha verification failed. Please try again.") from exc

    if not payload.get("success", False):
        logger.info("reCAPTCHA rejected: %s", payload.get("error-codes"))
        raise ValueError("Captcha verification failed. Please try again.")

    # reCAPTCHA v3 returns an "action" and "score". When present, validate action matches signup.
    action = payload.get("action")
    if action and action != "signup":
        logger.info("reCAPTCHA action mismatch: %s", action)
        raise ValueError("Captcha verification failed. Please try again.")
