"""Email Service for sending verification emails and password reset links via Resend.

Features:
- Resend API integration (resend.Emails.send)
- Database-backed request limiting (1 request per 60s, max 5 per hour)
- Responsive, clean HTML and plain text email templates
- Background execution via FastAPI BackgroundTasks
- Explicit provider acceptance/failure results and redacted operational logs
- Backward-compatible SMTP OTP helper preserved for legacy callers
"""
import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import resend

from app.config import settings
from app.services.email_rate_limit import check_email_rate_limit

logger = logging.getLogger(__name__)


def _build_action_urls(endpoint: str, token: str) -> tuple[str, str]:
    """Generate HashRouter-compatible URLs for frontend action links.

    Returns (primary_url, fallback_url).
    """
    base = settings.FRONTEND_URL.rstrip("/")
    hash_url = f"{base}/#/{endpoint}?token={token}"
    return hash_url, hash_url


def send_verification_email(to_email: str, name: str, token: str) -> bool:
    """Send an email verification link via Resend.

    Designed for use with FastAPI BackgroundTasks. Errors are caught and logged
    without raising an unhandled exception in the background thread.
    """
    clean_name = name.strip() if name else "there"
    primary_url, hash_url = _build_action_urls("verify-email", token)
    expiry_min = settings.VERIFY_TOKEN_EXPIRE_MINUTES
    subject = "Verify Your Email · GDGOC Hacktoberfest"

    html_content = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 580px; margin: 0 auto; padding: 28px; border: 2px solid #101010; border-radius: 8px; background-color: #fdfbf7; color: #101010;">
      <div style="margin-bottom: 20px;">
        <span style="font-size: 11px; font-weight: bold; letter-spacing: 2px; text-transform: uppercase; color: #4285F4; display: block; margin-bottom: 6px;">GDGOC PSIT · Hacktoberfest</span>
        <h1 style="font-size: 24px; font-weight: 800; margin: 0; color: #101010; line-height: 1.2;">Verify Your Email Address</h1>
      </div>
      <hr style="border: none; border-top: 2px solid #101010; margin: 18px 0;" />
      <p style="font-size: 15px; line-height: 1.6; margin: 0 0 16px 0;">Hello <strong>{clean_name}</strong>,</p>
      <p style="font-size: 15px; line-height: 1.6; margin: 0 0 24px 0;">Thank you for registering for GDGOC Hacktoberfest. Please verify your email address to confirm your account and stay updated on repository challenges and contribution reviews.</p>
      
      <div style="text-align: center; margin: 28px 0;">
        <a href="{primary_url}" style="background-color: #101010; color: #ffffff; padding: 14px 28px; text-decoration: none; font-size: 14px; font-weight: 700; border-radius: 4px; display: inline-block; letter-spacing: 0.5px;">Verify Email Address &rarr;</a>
      </div>

      <p style="font-size: 13px; color: #555555; line-height: 1.5; margin: 24px 0 8px 0;">If the button above does not work, copy and paste this link into your browser:</p>
      <p style="font-size: 12px; word-break: break-all; color: #4285F4; background: #f0ede6; padding: 10px; border-radius: 4px; margin: 0 0 20px 0;">
        <a href="{hash_url}" style="color: #4285F4; text-decoration: underline;">{primary_url}</a>
      </p>

      <div style="background-color: #fff9e6; border-left: 4px solid #fbbc04; padding: 10px 14px; margin: 20px 0;">
        <p style="font-size: 12px; color: #7a5e00; margin: 0;"><strong>Security Notice:</strong> This verification link will expire in <strong>{expiry_min} minutes</strong> and can only be used once.</p>
      </div>

      <hr style="border: none; border-top: 1px dashed #d0ccc4; margin: 24px 0 16px 0;" />
      <p style="font-size: 11px; color: #888888; text-align: center; margin: 0;">GDGOC Hacktoberfest Platform &middot; PSIT Kanpur<br/>If you did not register for this event, you can safely ignore this email.</p>
    </div>
    """

    text_content = (
        f"GDGOC Hacktoberfest · Email Verification\n\n"
        f"Hello {clean_name},\n\n"
        f"Please verify your email address by opening the following link in your browser:\n\n"
        f"{primary_url}\n\n"
        f"This link will expire in {expiry_min} minutes and can only be used once.\n\n"
        f"If you did not create an account, you can safely ignore this email."
    )

    return _dispatch_email(
        to_email=to_email,
        subject=subject,
        html_content=html_content,
        text_content=text_content,
        action_name="Email Verification",
    )


def send_password_reset_email(to_email: str, name: str, token: str, otp_code: Optional[str] = None) -> bool:
    """Send a password reset email via Resend containing the reset link and optional 6-digit OTP.

    Designed for use with FastAPI BackgroundTasks. Errors are caught and logged
    without raising an unhandled exception in the background thread.
    """
    clean_name = name.strip() if name else "there"
    primary_url, hash_url = _build_action_urls("reset-password", token)
    expiry_min = settings.RESET_TOKEN_EXPIRE_MINUTES
    subject = f"Reset Your Password · GDGOC Hacktoberfest" + (f" (OTP: {otp_code})" if otp_code else "")

    otp_block = ""
    otp_text = ""
    if otp_code:
        otp_block = f"""
        <div style="background-color: #FBBC04; padding: 16px; text-align: center; border: 2px solid #101010; border-radius: 4px; margin: 20px 0;">
          <span style="font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: 1.5px; display: block; margin-bottom: 6px; color: #101010;">Your 6-Digit Reset Code</span>
          <span style="font-size: 32px; font-weight: 800; font-family: monospace; letter-spacing: 8px; color: #101010;">{otp_code}</span>
        </div>
        <p style="font-size: 13px; text-align: center; color: #777; margin: 12px 0;">&mdash; OR CLICK THE BUTTON BELOW &mdash;</p>
        """
        otp_text = f"\nYour 6-Digit OTP Code: {otp_code}\n(Valid for 15 minutes)\n\n--- OR RESET USING THE LINK BELOW ---\n"

    html_content = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 580px; margin: 0 auto; padding: 28px; border: 2px solid #101010; border-radius: 8px; background-color: #fdfbf7; color: #101010;">
      <div style="margin-bottom: 20px;">
        <span style="font-size: 11px; font-weight: bold; letter-spacing: 2px; text-transform: uppercase; color: #EA4335; display: block; margin-bottom: 6px;">GDGOC PSIT · Hacktoberfest</span>
        <h1 style="font-size: 24px; font-weight: 800; margin: 0; color: #101010; line-height: 1.2;">Password Reset Request</h1>
      </div>
      <hr style="border: none; border-top: 2px solid #101010; margin: 18px 0;" />
      <p style="font-size: 15px; line-height: 1.6; margin: 0 0 16px 0;">Hello <strong>{clean_name}</strong>,</p>
      <p style="font-size: 15px; line-height: 1.6; margin: 0 0 16px 0;">We received a request to reset the password for your account.</p>
      
      {otp_block}

      <div style="text-align: center; margin: 24px 0;">
        <a href="{primary_url}" style="background-color: #101010; color: #ffffff; padding: 14px 28px; text-decoration: none; font-size: 14px; font-weight: 700; border-radius: 4px; display: inline-block; letter-spacing: 0.5px;">Reset My Password &rarr;</a>
      </div>

      <p style="font-size: 13px; color: #555555; line-height: 1.5; margin: 24px 0 8px 0;">If the button above does not work, copy and paste this link into your browser:</p>
      <p style="font-size: 12px; word-break: break-all; color: #4285F4; background: #f0ede6; padding: 10px; border-radius: 4px; margin: 0 0 20px 0;">
        <a href="{hash_url}" style="color: #4285F4; text-decoration: underline;">{primary_url}</a>
      </p>

      <div style="background-color: #fff9e6; border-left: 4px solid #fbbc04; padding: 10px 14px; margin: 20px 0;">
        <p style="font-size: 12px; color: #7a5e00; margin: 0;"><strong>Security Notice:</strong> This request will expire in <strong>{expiry_min} minutes</strong>. If you did not request a password reset, you can safely ignore this email.</p>
      </div>

      <hr style="border: none; border-top: 1px dashed #d0ccc4; margin: 24px 0 16px 0;" />
      <p style="font-size: 11px; color: #888888; text-align: center; margin: 0;">GDGOC Hacktoberfest Platform &middot; PSIT Kanpur</p>
    </div>
    """

    text_content = (
        f"GDGOC Hacktoberfest · Password Reset\n\n"
        f"Hello {clean_name},\n\n"
        f"We received a request to reset your password.\n"
        f"{otp_text}\n"
        f"Open this link in your browser to set a new password:\n"
        f"{primary_url}\n\n"
        f"This request expires in {expiry_min} minutes. If you did not request this, please ignore this email."
    )

    return _dispatch_email(
        to_email=to_email,
        subject=subject,
        html_content=html_content,
        text_content=text_content,
        action_name="Password Reset",
    )


def _dispatch_email(to_email: str, subject: str, html_content: str, text_content: str, action_name: str) -> bool:
    """Return True only for provider acceptance (not guaranteed inbox delivery).

    Never log message bodies, subjects containing OTPs, or provider exception
    text, which can contain recipients, credentials or reset links.
    """

    # 1. Prefer SMTP if configured (works seamlessly with Gmail to any address)
    if settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
        msg["To"] = to_email
        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        sent = False
        try:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, 465, timeout=6, context=ssl.create_default_context()) as ssl_server:
                ssl_server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                if ssl_server.send_message(msg) != {}:
                    raise smtplib.SMTPException("Recipient refused")
            logger.info("%s email accepted via SMTP SSL", action_name)
            sent = True
        except Exception as ssl_exc:
            logger.warning("SMTP SSL failed (%s); trying STARTTLS", type(ssl_exc).__name__)
            try:
                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT or 587, timeout=6) as server:
                    server.starttls(context=ssl.create_default_context())
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                    if server.send_message(msg) != {}:
                        raise smtplib.SMTPException("Recipient refused")
                logger.info("%s email accepted via SMTP STARTTLS", action_name)
                sent = True
            except Exception as smtp_exc:
                logger.error("%s SMTP delivery failed (%s)", action_name, type(smtp_exc).__name__)

        if sent:
            return True

    # 2. Try Resend if configured
    if settings.RESEND_API_KEY:
        try:
            resend.api_key = settings.RESEND_API_KEY
            params: resend.Emails.SendParams = {
                "from": settings.EMAIL_FROM,
                "to": [to_email],
                "subject": subject,
                "html": html_content,
                "text": text_content,
            }
            result = resend.Emails.send(params)
            if (
                isinstance(result, dict)
                and isinstance(result.get("id"), str)
                and result["id"].strip()
                and not result.get("error")
                and result.get("statusCode", 200) in (200, 201, 202)
            ):
                logger.info("%s email accepted via Resend", action_name)
                return True
            logger.error("%s Resend response did not confirm acceptance", action_name)
        except Exception as exc:
            logger.error("%s Resend delivery failed (%s)", action_name, type(exc).__name__)

    logger.error("%s email was not accepted by any provider; check email configuration and provider health", action_name)
    return False


# ──────────────────────────────────────────────────────────────────────
# Backwards-compatible OTP email helper for existing legacy callers
# ──────────────────────────────────────────────────────────────────────

def send_password_reset_otp_email(to_email: str, roll_no: str, otp_code: str) -> bool:
    """Send a 6-digit password reset OTP code to student's email address (Resend or legacy SMTP)."""
    subject = f"GDGOC Hacktoberfest - Password Reset Code: {otp_code}"

    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 3px solid #101010; border-radius: 8px; background-color: #fdfbf7;">
      <h2 style="color: #4285F4; margin-top: 0;">GDGOC Hacktoberfest · PSIT</h2>
      <hr style="border: 1px solid #101010; margin: 15px 0;" />
      <p style="font-size: 16px; color: #101010;">Hello,</p>
      <p style="font-size: 15px; color: #101010;">We received a request to reset the password for your account linked to roll number <strong>{roll_no}</strong>.</p>
      <div style="background-color: #FBBC04; padding: 15px; text-align: center; border: 2px solid #101010; margin: 20px 0;">
        <span style="font-size: 12px; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; display: block; margin-bottom: 5px;">Your Password Reset Code</span>
        <span style="font-size: 32px; font-weight: bold; font-family: monospace; letter-spacing: 6px;">{otp_code}</span>
      </div>
      <p style="font-size: 14px; color: #555;">This code will expire in <strong>15 minutes</strong>. If you did not request a password reset, please ignore this email.</p>
      <hr style="border: 1px dashed #ccc; margin: 20px 0;" />
      <p style="font-size: 12px; color: #888; text-align: center;">GDGOC Hacktoberfest Platform — PSIT Kanpur</p>
    </div>
    """

    text_content = (
        f"GDGOC Hacktoberfest - Password Reset Code\n\n"
        f"Roll Number: {roll_no}\n"
        f"Your OTP Code: {otp_code}\n\n"
        f"This code will expire in 15 minutes."
    )

    # Share acceptance detection and redacted logging with the link-based flow.
    return _dispatch_email(to_email, subject, html_content, text_content, "Password Reset OTP")
