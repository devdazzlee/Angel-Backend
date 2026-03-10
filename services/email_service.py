"""
Custom SMTP email service (Python equivalent of Nodemailer).
Sends signup confirmation, password reset, subscription, and other emails via your SMTP.
Bypasses Supabase's built-in email to avoid 504 timeouts with Office 365 etc.

Environment variables:
  SMTP_HOST      - e.g. smtp.office365.com
  SMTP_PORT      - e.g. 587
  SMTP_USER      - e.g. support@founderport.ai
  SMTP_PASSWORD  - App password for Office 365 (if MFA enabled)
  SMTP_FROM_NAME - Sender display name, e.g. Founderport
"""
import asyncio
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def _get_smtp_config():
    host = os.getenv("SMTP_HOST", "smtp.office365.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    from_name = os.getenv("SMTP_FROM_NAME", "Founderport")
    return host, port, user, password, from_name


def _send_email(to_email: str, subject: str, html_body: str, text_body: str = None) -> bool:
    """Send email via SMTP. Returns True on success."""
    host, port, user, password, from_name = _get_smtp_config()
    if not user or not password:
        logger.error("SMTP_USER and SMTP_PASSWORD must be set in .env")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{user}>"
        msg["To"] = to_email

        if text_body:
            msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(user, to_email, msg.as_string())

        logger.info(f"Email sent to {to_email}: {subject}")
        return True
    except Exception as e:
        logger.error(f"SMTP send failed: {e}")
        return False


def send_password_reset_email(to_email: str, reset_link: str) -> bool:
    """Send password reset email with link."""
    subject = "Reset your Founderport password"
    html_body = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
      <h2>Reset your password</h2>
      <p>You requested a password reset for your Founderport account.</p>
      <p>Click the button below to set a new password:</p>
      <p style="margin: 24px 0;">
        <a href="{reset_link}" style="background: #0d9488; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">Reset password</a>
      </p>
      <p>Or copy this link: <a href="{reset_link}">{reset_link}</a></p>
      <p style="color: #666; font-size: 14px;">This link expires in 1 hour. If you didn't request this, you can ignore this email.</p>
      <p>— The Founderport Team</p>
    </div>
    """
    text_body = f"Reset your password: {reset_link}\n\nThis link expires in 1 hour."
    return _send_email(to_email, subject, html_body, text_body)


def send_signup_confirmation_email(to_email: str, confirm_link: str) -> bool:
    """Send signup confirmation email with link."""
    subject = "Confirm your Founderport account"
    html_body = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
      <h2>Confirm your email</h2>
      <p>Thanks for signing up for Founderport!</p>
      <p>Click the button below to confirm your email address:</p>
      <p style="margin: 24px 0;">
        <a href="{confirm_link}" style="background: #0d9488; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">Confirm email</a>
      </p>
      <p>Or copy this link: <a href="{confirm_link}">{confirm_link}</a></p>
      <p style="color: #666; font-size: 14px;">If you didn't create an account, you can ignore this email.</p>
      <p>— The Founderport Team</p>
    </div>
    """
    text_body = f"Confirm your email: {confirm_link}"
    return _send_email(to_email, subject, html_body, text_body)


def _subscription_base_styles() -> str:
    """Shared styles for subscription emails."""
    return """
    font-family: sans-serif; max-width: 600px; margin: 0 auto;
    """


async def send_subscription_confirmation_email(
    user_email: str,
    amount: float,
    currency: str,
    subscription_start_date: str,
    subscription_end_date: str,
    last4: str = None,
) -> bool:
    """Send subscription confirmation email."""
    amt = f"{currency.upper()} {amount:.2f}"
    last4_line = f"<p>Payment method: •••• {last4}</p>" if last4 else ""
    subject = "Your Founderport subscription is active"
    html_body = f"""
    <div style="{_subscription_base_styles()}">
      <h2>Welcome to Founderport</h2>
      <p>Your subscription is now active.</p>
      <p><strong>Amount:</strong> {amt}</p>
      <p><strong>Billing period:</strong> {subscription_start_date[:10]} – {subscription_end_date[:10]}</p>
      {last4_line}
      <p>— The Founderport Team</p>
    </div>
    """
    text_body = f"Your subscription is active. Amount: {amt}. Period: {subscription_start_date[:10]} – {subscription_end_date[:10]}."
    return await asyncio.to_thread(_send_email, user_email, subject, html_body, text_body)


async def send_subscription_renewal_receipt_email(
    user_email: str,
    amount: float,
    currency: str,
    subscription_start_date: str,
    subscription_end_date: str,
    last4: str = None,
) -> bool:
    """Send subscription renewal receipt email."""
    amt = f"{currency.upper()} {amount:.2f}"
    last4_line = f"<p>Payment method: •••• {last4}</p>" if last4 else ""
    subject = "Your Founderport subscription renewal"
    html_body = f"""
    <div style="{_subscription_base_styles()}">
      <h2>Renewal receipt</h2>
      <p>Your Founderport subscription has been renewed.</p>
      <p><strong>Amount:</strong> {amt}</p>
      <p><strong>Billing period:</strong> {subscription_start_date[:10]} – {subscription_end_date[:10]}</p>
      {last4_line}
      <p>— The Founderport Team</p>
    </div>
    """
    text_body = f"Subscription renewed. Amount: {amt}. Period: {subscription_start_date[:10]} – {subscription_end_date[:10]}."
    return await asyncio.to_thread(_send_email, user_email, subject, html_body, text_body)


async def send_subscription_expiring_email(
    user_email: str,
    subscription_end_date: str,
) -> bool:
    """Send email when subscription is set to expire at period end."""
    subject = "Your Founderport subscription is expiring"
    html_body = f"""
    <div style="{_subscription_base_styles()}">
      <h2>Subscription expiring</h2>
      <p>Your Founderport subscription will end on <strong>{subscription_end_date[:10]}</strong>.</p>
      <p>To continue using Founderport, renew before this date.</p>
      <p>— The Founderport Team</p>
    </div>
    """
    text_body = f"Your subscription will end on {subscription_end_date[:10]}. Renew before this date to continue."
    return await asyncio.to_thread(_send_email, user_email, subject, html_body, text_body)


async def send_subscription_expired_email(
    user_email: str,
    subscription_end_date: str,
) -> bool:
    """Send email when subscription has ended."""
    subject = "Your Founderport subscription has ended"
    html_body = f"""
    <div style="{_subscription_base_styles()}">
      <h2>Subscription ended</h2>
      <p>Your Founderport subscription ended on <strong>{subscription_end_date[:10]}</strong>.</p>
      <p>You can resubscribe anytime to continue using Founderport.</p>
      <p>— The Founderport Team</p>
    </div>
    """
    text_body = f"Your subscription ended on {subscription_end_date[:10]}. Resubscribe to continue."
    return await asyncio.to_thread(_send_email, user_email, subject, html_body, text_body)


async def send_billing_problem_email(
    user_email: str,
    amount: float,
    currency: str,
    invoice_url: str = None,
) -> bool:
    """Send email when a payment has failed."""
    amt = f"{currency.upper()} {amount:.2f}"
    invoice_line = ""
    if invoice_url:
        invoice_line = f'<p><a href="{invoice_url}" style="background: #0d9488; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">Update payment method</a></p>'
    subject = "Action needed: your Founderport payment failed"
    html_body = f"""
    <div style="{_subscription_base_styles()}">
      <h2>Payment failed</h2>
      <p>We couldn't process your payment of {amt}.</p>
      <p>Please update your payment method to avoid interruption of your service.</p>
      {invoice_line}
      <p>— The Founderport Team</p>
    </div>
    """
    text_body = f"Payment of {amt} failed. Update your payment method. {invoice_url or ''}"
    return await asyncio.to_thread(_send_email, user_email, subject, html_body, text_body)


async def send_subscription_cancellation_email(
    user_email: str,
    subscription_end_date: str = None,
) -> bool:
    """Send email when user cancels their subscription (cancel_at_period_end)."""
    end_line = f"<p>Your access continues until <strong>{subscription_end_date[:10]}</strong>.</p>" if subscription_end_date else ""
    subject = "Your Founderport subscription has been cancelled"
    html_body = f"""
    <div style="{_subscription_base_styles()}">
      <h2>Subscription cancelled</h2>
      <p>Your Founderport subscription has been cancelled.</p>
      {end_line}
      <p>You can resubscribe anytime.</p>
      <p>— The Founderport Team</p>
    </div>
    """
    text_body = f"Your subscription has been cancelled. {f'Access until {subscription_end_date[:10]}' if subscription_end_date else ''}"
    return await asyncio.to_thread(_send_email, user_email, subject, html_body, text_body)
