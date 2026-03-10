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
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def _get_smtp_config():
    host = os.getenv("SMTP_HOST", "smtp.office365.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    # Support both SMTP_USER and SMTP_USERNAME for compatibility
    user = os.getenv("SMTP_USER") or os.getenv("SMTP_USERNAME", "")
    password = os.getenv("SMTP_PASSWORD", "")
    from_name = os.getenv("SMTP_FROM_NAME", "Founderport")
    # Use SMTP_FROM_EMAIL, fallback to SMTP_USER if it looks like an email
    from_email = os.getenv("SMTP_FROM_EMAIL", "")
    if not from_email and user and "@" in user:
        from_email = user
    # Determine if we should use SSL (port 465) or TLS (port 587)
    use_ssl = port == 465 or os.getenv("SMTP_USE_TLS", "true").lower() in ("false", "0", "no")
    return host, port, user, password, from_name, from_email, use_ssl


def _send_email(to_email: str, subject: str, html_body: str, text_body: str = None) -> bool:
    """Send email via SMTP. Returns True on success."""
    host, port, user, password, from_name, from_email, use_ssl = _get_smtp_config()
    if not user or not password:
        logger.error("SMTP_USER (or SMTP_USERNAME) and SMTP_PASSWORD must be set in .env")
        return False
    
    if not from_email:
        logger.error("SMTP_FROM_EMAIL must be set in .env file")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{from_email}>"
        msg["To"] = to_email

        if text_body:
            msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        # Use SSL for port 465 (Resend, Gmail SSL), TLS for port 587 (Office 365, Gmail TLS)
        if use_ssl:
            # Port 465 uses SSL directly
            with smtplib.SMTP_SSL(host, port) as server:
                server.login(user, password)
                server.sendmail(from_email, to_email, msg.as_string())
        else:
            # Port 587 uses STARTTLS
            with smtplib.SMTP(host, port) as server:
                server.starttls()
                server.login(user, password)
                server.sendmail(from_email, to_email, msg.as_string())

        logger.info(f"Email sent to {to_email}: {subject}")
        return True
    except Exception as e:
        logger.error(f"SMTP send failed: {e}")
        return False


def send_password_reset_email(to_email: str, reset_link: str) -> bool:
    """Send password reset email with link."""
    subject = "Reset your Founderport password"
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f5f5f5;">
      <table role="presentation" style="width: 100%; border-collapse: collapse; background-color: #f5f5f5;">
        <tr>
          <td style="padding: 40px 20px;">
            <table role="presentation" style="width: 100%; max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); border-collapse: collapse;">
              <!-- Header -->
              <tr>
                <td style="padding: 40px 40px 30px; text-align: center; background: linear-gradient(135deg, #0d9488 0%, #14b8a6 100%); border-radius: 12px 12px 0 0;">
                  <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 600; letter-spacing: -0.5px;">Reset Your Password</h1>
                </td>
              </tr>
              <!-- Content -->
              <tr>
                <td style="padding: 40px 40px 30px;">
                  <p style="margin: 0 0 16px; color: #1f2937; font-size: 16px; line-height: 1.6;">Hello,</p>
                  <p style="margin: 0 0 24px; color: #4b5563; font-size: 16px; line-height: 1.6;">You requested a password reset for your Founderport account. Click the button below to set a new password:</p>
                  
                  <!-- CTA Button -->
                  <table role="presentation" style="width: 100%; border-collapse: collapse; margin: 32px 0;">
                    <tr>
                      <td style="text-align: center;">
                        <a href="{reset_link}" style="display: inline-block; background: linear-gradient(135deg, #0d9488 0%, #14b8a6 100%); color: #ffffff; text-decoration: none; padding: 16px 32px; border-radius: 8px; font-weight: 600; font-size: 16px; box-shadow: 0 4px 6px rgba(13, 148, 136, 0.3); transition: all 0.3s ease;">Reset Password</a>
                      </td>
                    </tr>
                  </table>
                  
                  <!-- Alternative Link -->
                  <p style="margin: 32px 0 16px; color: #6b7280; font-size: 14px; line-height: 1.5;">Or copy and paste this link into your browser:</p>
                  <p style="margin: 0 0 32px; padding: 12px; background-color: #f9fafb; border-radius: 6px; word-break: break-all;">
                    <a href="{reset_link}" style="color: #0d9488; text-decoration: none; font-size: 13px; line-height: 1.5;">{reset_link}</a>
                  </p>
                  
                  <!-- Security Notice -->
                  <div style="margin: 32px 0; padding: 16px; background-color: #fef3c7; border-left: 4px solid #f59e0b; border-radius: 4px;">
                    <p style="margin: 0; color: #92400e; font-size: 14px; line-height: 1.5;">
                      <strong>⏰ This link expires in 1 hour.</strong><br>
                      If you didn't request this password reset, you can safely ignore this email.
                    </p>
                  </div>
                </td>
              </tr>
              <!-- Footer -->
              <tr>
                <td style="padding: 30px 40px; text-align: center; background-color: #f9fafb; border-radius: 0 0 12px 12px; border-top: 1px solid #e5e7eb;">
                  <p style="margin: 0 0 8px; color: #6b7280; font-size: 14px;">— The Founderport Team</p>
                  <p style="margin: 0; color: #9ca3af; font-size: 12px;">© {datetime.now().year} Founderport. All rights reserved.</p>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """
    text_body = f"""Reset your Founderport password

You requested a password reset for your Founderport account.

Click this link to reset your password:
{reset_link}

This link expires in 1 hour. If you didn't request this, you can safely ignore this email.

— The Founderport Team"""
    return _send_email(to_email, subject, html_body, text_body)


def send_signup_confirmation_email(to_email: str, confirm_link: str) -> bool:
    """Send signup confirmation email with link."""
    subject = "Welcome to Founderport - Confirm your email"
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f5f5f5;">
      <table role="presentation" style="width: 100%; border-collapse: collapse; background-color: #f5f5f5;">
        <tr>
          <td style="padding: 40px 20px;">
            <table role="presentation" style="width: 100%; max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); border-collapse: collapse;">
              <!-- Header -->
              <tr>
                <td style="padding: 40px 40px 30px; text-align: center; background: linear-gradient(135deg, #0d9488 0%, #14b8a6 100%); border-radius: 12px 12px 0 0;">
                  <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 600; letter-spacing: -0.5px;">Welcome to Founderport! 🎉</h1>
                </td>
              </tr>
              <!-- Content -->
              <tr>
                <td style="padding: 40px 40px 30px;">
                  <p style="margin: 0 0 16px; color: #1f2937; font-size: 16px; line-height: 1.6;">Hello,</p>
                  <p style="margin: 0 0 24px; color: #4b5563; font-size: 16px; line-height: 1.6;">Thanks for signing up for Founderport! We're excited to have you on board. To get started, please confirm your email address by clicking the button below:</p>
                  
                  <!-- CTA Button -->
                  <table role="presentation" style="width: 100%; border-collapse: collapse; margin: 32px 0;">
                    <tr>
                      <td style="text-align: center;">
                        <a href="{confirm_link}" style="display: inline-block; background: linear-gradient(135deg, #0d9488 0%, #14b8a6 100%); color: #ffffff; text-decoration: none; padding: 16px 32px; border-radius: 8px; font-weight: 600; font-size: 16px; box-shadow: 0 4px 6px rgba(13, 148, 136, 0.3); transition: all 0.3s ease;">Confirm Email Address</a>
                      </td>
                    </tr>
                  </table>
                  
                  <!-- Alternative Link -->
                  <p style="margin: 32px 0 16px; color: #6b7280; font-size: 14px; line-height: 1.5;">Or copy and paste this link into your browser:</p>
                  <p style="margin: 0 0 32px; padding: 12px; background-color: #f9fafb; border-radius: 6px; word-break: break-all;">
                    <a href="{confirm_link}" style="color: #0d9488; text-decoration: none; font-size: 13px; line-height: 1.5;">{confirm_link}</a>
                  </p>
                  
                  <!-- Security Notice -->
                  <div style="margin: 32px 0; padding: 16px; background-color: #f0f9ff; border-left: 4px solid #0d9488; border-radius: 4px;">
                    <p style="margin: 0; color: #0c4a6e; font-size: 14px; line-height: 1.5;">
                      <strong>💡 What's next?</strong><br>
                      Once you confirm your email, you'll have full access to all Founderport features. If you didn't create an account, you can safely ignore this email.
                    </p>
                  </div>
                </td>
              </tr>
              <!-- Footer -->
              <tr>
                <td style="padding: 30px 40px; text-align: center; background-color: #f9fafb; border-radius: 0 0 12px 12px; border-top: 1px solid #e5e7eb;">
                  <p style="margin: 0 0 8px; color: #6b7280; font-size: 14px;">— The Founderport Team</p>
                  <p style="margin: 0; color: #9ca3af; font-size: 12px;">© {datetime.now().year} Founderport. All rights reserved.</p>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """
    text_body = f"""Welcome to Founderport!

Thanks for signing up! Please confirm your email address by clicking this link:

{confirm_link}

If you didn't create an account, you can safely ignore this email.

— The Founderport Team"""
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
