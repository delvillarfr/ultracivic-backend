"""
Email Service for Ultra Civic

Handles sending password reset and verification emails using SMTP.
Supports both development (console output) and production (SMTP) modes.
"""

import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import get_settings

settings = get_settings()


async def send_reset_password_email(email: str, token: str) -> None:
    """Send password reset email with token link."""
    
    # Development mode - just print to console
    if not settings.smtp_username or not settings.smtp_password.get_secret_value():
        print(f"[DEV] Password reset email for {email}")
        print(f"[DEV] Reset link: https://ultracivic.com/reset-password.html?token={token}")
        return
    
    # Production mode - send actual email
    reset_url = f"https://ultracivic.com/reset-password.html?token={token}"
    
    message = MIMEMultipart("alternative")
    message["Subject"] = "Ultra Civic - Reset Your Password"
    message["From"] = settings.smtp_from_email
    message["To"] = email
    
    text_content = f"""
    Hi there,
    
    You requested to reset your password for Ultra Civic.
    
    Click the link below to reset your password:
    {reset_url}
    
    This link will expire in 1 hour for security reasons.
    
    If you didn't request this, please ignore this email.
    
    Best regards,
    Ultra Civic Team
    """
    
    html_content = f"""
    <html>
    <body>
        <h2>Reset Your Password</h2>
        <p>Hi there,</p>
        <p>You requested to reset your password for Ultra Civic.</p>
        <p><a href="{reset_url}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Reset Password</a></p>
        <p>This link will expire in 1 hour for security reasons.</p>
        <p>If you didn't request this, please ignore this email.</p>
        <p>Best regards,<br>Ultra Civic Team</p>
    </body>
    </html>
    """
    
    text_part = MIMEText(text_content, "plain")
    html_part = MIMEText(html_content, "html")
    
    message.attach(text_part)
    message.attach(html_part)
    
    try:
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            start_tls=True,
            username=settings.smtp_username,
            password=settings.smtp_password.get_secret_value(),
        )
        print(f"[EMAIL] Password reset email sent to {email}")
    except Exception as e:
        print(f"[ERROR] Failed to send email to {email}: {e}")
        # Fallback to console in case of email failure
        print(f"[DEV] Reset link: {reset_url}")


async def send_verification_email(email: str, token: str) -> None:
    """Send email verification email with token link."""
    
    # Development mode - just print to console
    if not settings.smtp_username or not settings.smtp_password.get_secret_value():
        print(f"[DEV] Verification email for {email}")
        print(f"[DEV] Verification link: https://ultracivic.com/verify.html?token={token}")
        return
    
    # Production mode - send actual email
    verify_url = f"https://ultracivic.com/verify.html?token={token}"
    
    message = MIMEMultipart("alternative")
    message["Subject"] = "Ultra Civic - Verify Your Email"
    message["From"] = settings.smtp_from_email
    message["To"] = email
    
    text_content = f"""
    Hi there,
    
    Welcome to Ultra Civic! Please verify your email address.
    
    Click the link below to verify your email:
    {verify_url}
    
    If you didn't create this account, please ignore this email.
    
    Best regards,
    Ultra Civic Team
    """
    
    html_content = f"""
    <html>
    <body>
        <h2>Verify Your Email</h2>
        <p>Hi there,</p>
        <p>Welcome to Ultra Civic! Please verify your email address.</p>
        <p><a href="{verify_url}" style="background-color: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Verify Email</a></p>
        <p>If you didn't create this account, please ignore this email.</p>
        <p>Best regards,<br>Ultra Civic Team</p>
    </body>
    </html>
    """
    
    text_part = MIMEText(text_content, "plain")
    html_part = MIMEText(html_content, "html")
    
    message.attach(text_part)
    message.attach(html_part)
    
    try:
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            start_tls=True,
            username=settings.smtp_username,
            password=settings.smtp_password.get_secret_value(),
        )
        print(f"[EMAIL] Verification email sent to {email}")
    except Exception as e:
        print(f"[ERROR] Failed to send email to {email}: {e}")
        # Fallback to console in case of email failure
        print(f"[DEV] Verification link: {verify_url}")