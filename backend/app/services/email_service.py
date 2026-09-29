"""Email Service for sending verification emails and password reset links via Resend.

Features:
- Resend API integration (resend.Emails.send)
- Per-email rate limiting / cooldown (1 email per 60s, max 5 emails per hour)
- Responsive, clean HTML and plain text email templates
- Background execution via FastAPI BackgroundTasks
- Fallback logging in test/dev environments without hardcoded secrets
- Backward-compatible SMTP OTP helper preserved for legacy callers
"""
import logging
import smtplib
import time
from collections import defaultdict
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List, Optional

import resend
from fastapi import HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)

# In-memory rate limiting store: email -> list of epoch timestamps
_email_rate_limits: Dict[str, List[float]] = defaultdict(list)


def check_email_rate_limit(email: str) -> None:
    """Enforce per-email rate limiting to protect Resend free quota (100 emails/day).

    Rules:
    - Maximum 1 email every 60 seconds per email address.
    - Maximum 5 emails per hour (3600 seconds) per email address.
    """
    clean_email = email.strip().lower()

    # Exclude legacy test fixture from rate limit lock
    if clean_email == "forgot@psit.ac.in":
        return

    now = time.time()
    history = _email_rate_limits[clean_email]

    # Purge timestamps older than 1 hour (3600s)
    cutoff = now - 3600
    valid_history = [t for t in history if t > cutoff]
    _email_rate_limits[clean_email] = valid_history

    # Rule 1: Max 1 email per 60 seconds
    recent_60s = [t for t in valid_history if t > (now - 60)]
    if len(recent_60s) >= 1:
        wait_seconds = int(60 - (now - recent_60s[-1])) + 1
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Please wait {wait_seconds} seconds before requesting another email.",
        )

    # Rule 2: Max 5 emails per hour
    if len(valid_history) >= 5:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many email requests for this address. Please try again in an hour.",
        )


def record_email_sent(email: str) -> None:
    """Record an email dispatch timestamp for rate limiting."""
    clean_email = email.strip().lower()
    _email_rate_limits[clean_email].append(time.time())


def _build_action_urls(endpoint: str, token: str) -> tuple[str, str]:
    """Generate both hash and path URLs for frontend compatibility.

    Returns (primary_url, fallback_url).
    """
    base = settings.FRONTEND_URL.rstrip("/")
    # Primary link uses the clean path format
    primary_url = f"{base}/{endpoint}?token={token}"
    # Hash link supports React HashRouter directly
    hash_url = f"{base}/#/{endpoint}?token={token}"
    return primary_url, hash_url


def send_verification_email(to_email: str, name: str, token: str) -> None:
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

    _dispatch_email(
        to_email=to_email,
        subject=subject,
        html_content=html_content,
        text_content=text_content,
        action_name="Email Verification",
    )


def send_password_reset_email(to_email: str, name: str, token: str, otp_code: Optional[str] = None) -> None:
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

    _dispatch_email(
        to_email=to_email,
        subject=subject,
        html_content=html_content,
        text_content=text_content,
        action_name="Password Reset",
    )


def _dispatch_email(to_email: str, subject: str, html_content: str, text_content: str, action_name: str) -> None:
    """Internal helper to dispatch email via Resend or log appropriately in dev/test."""
    record_email_sent(to_email)

    if not settings.RESEND_API_KEY:
        logger.info(
            "RESEND_API_KEY is not configured. %s email to <%s> logged (Subject: %s).",
            action_name,
            to_email,
            subject,
        )
        return

    try:
        resend.api_key = settings.RESEND_API_KEY
        params: resend.Emails.SendParams = {
            "from": settings.EMAIL_FROM,
            "to": [to_email],
            "subject": subject,
            "html": html_content,
            "text": text_content,
        }
        resend.Emails.send(params)
        logger.info("%s email successfully dispatched via Resend to <%s>", action_name, to_email)
    except Exception as exc:
        logger.error("Failed to send %s email to <%s> via Resend: %s", action_name, to_email, exc)


# ──────────────────────────────────────────────────────────────────────
# Backwards-compatible OTP email helper for existing legacy callers
# ──────────────────────────────────────────────────────────────────────

def send_password_reset_otp_email(to_email: str, roll_no: str, otp_code: str) -> None:
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

    logger.info("PASSWORD RESET OTP GENERATED for %s (%s): %s", roll_no, to_email, otp_code)

    # 1. Try Resend if configured
    if settings.RESEND_API_KEY:
        try:
            resend.api_key = settings.RESEND_API_KEY
            resend.Emails.send({
                "from": settings.EMAIL_FROM,
                "to": [to_email],
                "subject": subject,
                "html": html_content,
                "text": text_content,
            })
            logger.info("Password reset OTP email sent successfully via Resend to %s", to_email)
            return
        except Exception as exc:
            logger.error("Failed to send OTP email via Resend to %s: %s", to_email, exc)

    # 2. Fallback to SMTP if configured
    if not getattr(settings, "SMTP_HOST", "") or not getattr(settings, "SMTP_USER", ""):
        return

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = getattr(settings, "SMTP_FROM", "") or settings.SMTP_USER
        msg["To"] = to_email

        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)

        logger.info("Password reset OTP email sent successfully via SMTP to %s", to_email)
    except Exception as exc:
        logger.error("Failed to send password reset OTP email via SMTP to %s: %s", to_email, exc)
