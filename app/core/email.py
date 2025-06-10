"""
Email Service for Ultra Civic

Handles sending password reset and verification emails using Resend.
Supports both development (console output) and production (Resend API) modes.
"""

try:
    import resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False
    resend = None

from app.core.config import get_settings

settings = get_settings()


async def send_reset_password_email(email: str, token: str) -> None:
    """Send password reset email with token link."""
    
    reset_url = f"https://ultracivic.com/reset-password.html?token={token}"
    
    # Development mode or no Resend - just print to console
    if not settings.resend_api_key.get_secret_value() or not RESEND_AVAILABLE:
        print(f"[DEV] Password reset email for {email}")
        print(f"[DEV] Reset link: {reset_url}")
        return
    
    # Production mode - send via Resend
    resend.api_key = settings.resend_api_key.get_secret_value()
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Reset Your Password</title>
    </head>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: rgb(23, 23, 130);">Ultra Civic</h1>
        </div>
        
        <h2 style="color: #333;">Reset Your Password</h2>
        <p>Hi there,</p>
        <p>You requested to reset your password for Ultra Civic.</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{reset_url}" 
               style="background-color: rgb(23, 23, 130); color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                Reset Password
            </a>
        </div>
        
        <p>This link will expire in 1 hour for security reasons.</p>
        <p>If you didn't request this, please ignore this email.</p>
        
        <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
        <p style="color: #666; font-size: 14px;">
            Best regards,<br>
            Ultra Civic Team
        </p>
    </body>
    </html>
    """
    
    try:
        params = {
            "from": settings.from_email,
            "to": [email],
            "subject": "Ultra Civic - Reset Your Password",
            "html": html_content,
        }
        
        resend.Emails.send(params)
        print(f"[EMAIL] Password reset email sent to {email}")
        
    except Exception as e:
        print(f"[ERROR] Failed to send email to {email}: {e}")
        # Fallback to console in case of email failure
        print(f"[DEV] Reset link: {reset_url}")


async def send_verification_email(email: str, token: str) -> None:
    """Send email verification email with token link."""
    
    verify_url = f"https://ultracivic.com/verify.html?token={token}"
    
    # Development mode or no Resend - just print to console
    if not settings.resend_api_key.get_secret_value() or not RESEND_AVAILABLE:
        print(f"[DEV] Verification email for {email}")
        print(f"[DEV] Verification link: {verify_url}")
        return
    
    # Production mode - send via Resend
    resend.api_key = settings.resend_api_key.get_secret_value()
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Verify Your Email</title>
    </head>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: rgb(23, 23, 130);">Ultra Civic</h1>
        </div>
        
        <h2 style="color: #333;">Verify Your Email</h2>
        <p>Hi there,</p>
        <p>Welcome to Ultra Civic! Please verify your email address to complete your registration.</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{verify_url}" 
               style="background-color: #28a745; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                Verify Email
            </a>
        </div>
        
        <p>If you didn't create this account, please ignore this email.</p>
        
        <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
        <p style="color: #666; font-size: 14px;">
            Best regards,<br>
            Ultra Civic Team
        </p>
    </body>
    </html>
    """
    
    try:
        params = {
            "from": settings.from_email,
            "to": [email],
            "subject": "Ultra Civic - Verify Your Email",
            "html": html_content,
        }
        
        resend.Emails.send(params)
        print(f"[EMAIL] Verification email sent to {email}")
        
    except Exception as e:
        print(f"[ERROR] Failed to send email to {email}: {e}")
        # Fallback to console in case of email failure
        print(f"[DEV] Verification link: {verify_url}")


async def send_magic_link_email(email: str, magic_link_url: str, expires_in_minutes: int = 5) -> None:
    """Send magic link email for passwordless authentication."""
    
    # Development mode or no Resend - just print to console
    if not settings.resend_api_key.get_secret_value() or not RESEND_AVAILABLE:
        print(f"[DEV] Magic link email for {email}")
        print(f"[DEV] Magic link: {magic_link_url}")
        print(f"[DEV] Expires in {expires_in_minutes} minutes")
        return
    
    # Production mode - send via Resend
    resend.api_key = settings.resend_api_key.get_secret_value()
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Your Ultra Civic Sign-In Link</title>
    </head>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: rgb(23, 23, 130);">Ultra Civic</h1>
        </div>
        
        <h2 style="color: #333;">Sign In to Ultra Civic</h2>
        <p>Hi there,</p>
        <p>You requested to sign in to Ultra Civic. Click the button below to access your account:</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{magic_link_url}" 
               style="background-color: rgb(23, 23, 130); color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                Sign In to Ultra Civic
            </a>
        </div>
        
        <p><strong>This link expires in {expires_in_minutes} minutes</strong> for security reasons.</p>
        <p>If you didn't request this sign-in link, please ignore this email.</p>
        
        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <p style="margin: 0; font-size: 14px; color: #666;">
                <strong>Security tip:</strong> We will never ask for your password via email. 
                This magic link provides secure, passwordless access to your account.
            </p>
        </div>
        
        <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
        <p style="color: #666; font-size: 14px;">
            Best regards,<br>
            Ultra Civic Team<br>
            <a href="https://ultracivic.com" style="color: rgb(23, 23, 130);">ultracivic.com</a>
        </p>
    </body>
    </html>
    """
    
    try:
        params = {
            "from": settings.from_email,
            "to": [email],
            "subject": "Your Ultra Civic Sign-In Link",
            "html": html_content,
        }
        
        resend.Emails.send(params)
        print(f"[EMAIL] Magic link email sent to {email}")
        
    except Exception as e:
        print(f"[ERROR] Failed to send magic link email to {email}: {e}")
        # Fallback to console in case of email failure
        print(f"[DEV] Magic link: {magic_link_url}")
        print(f"[DEV] Expires in {expires_in_minutes} minutes")