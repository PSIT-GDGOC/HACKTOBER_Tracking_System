"""Email Service for sending notifications and OTP verification codes.

Uses standard Python smtplib with STARTTLS.
Falls back to clean logger outputs in development / test environments when SMTP settings are unconfigured.
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings

logger = logging.getLogger(__name__)


def send_password_reset_otp_email(to_email: str, roll_no: str, otp_code: str) -> None:
    """Send a 6-digit password reset OTP code to student's email address."""
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

    # Always log the OTP code for development / local debugging
    logger.info("PASSWORD RESET OTP GENERATED for %s (%s): %s", roll_no, to_email, otp_code)

    if not settings.SMTP_HOST or not settings.SMTP_USER:
        logger.info("SMTP_HOST or SMTP_USER not set. Email notification logged above.")
        return

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
        msg["To"] = to_email

        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)

        logger.info("Password reset OTP email sent successfully to %s", to_email)
    except Exception as exc:
        logger.error("Failed to send password reset OTP email to %s: %s", to_email, exc)
