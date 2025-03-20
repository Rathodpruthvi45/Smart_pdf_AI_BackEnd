from aiosmtplib import SMTP
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Environment, PackageLoader, select_autoescape
import os
from pathlib import Path
from ..core.config import settings
import secrets
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from ..models.user import User, VerificationToken, PasswordResetToken

# Create Jinja2 environment for email templates
templates_path = Path(__file__).parent.parent / "templates"
if not templates_path.exists():
    os.makedirs(templates_path)

# Create email templates directory if it doesn't exist
email_templates_path = templates_path / "email"
if not email_templates_path.exists():
    os.makedirs(email_templates_path)

# Create verification email template if it doesn't exist
verification_template_path = email_templates_path / "verification.html"
if not verification_template_path.exists():
    with open(verification_template_path, "w") as f:
        f.write(
            """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Email Verification</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background-color: #4a69bd; color: white; padding: 10px; text-align: center; }
        .content { padding: 20px; border: 1px solid #ddd; }
        .button { display: inline-block; background-color: #4a69bd; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; }
        .footer { margin-top: 20px; font-size: 12px; color: #777; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Email Verification</h1>
        </div>
        <div class="content">
            <p>Hello {{ username }},</p>
            <p>Thank you for registering. Please verify your email address by clicking the button below:</p>
            <p style="text-align: center;">
                <a href="{{ verification_url }}" class="button">Verify Email</a>
            </p>
            <p>Or copy and paste the following URL into your browser:</p>
            <p>{{ verification_url }}</p>
            <p>This link will expire in 24 hours.</p>
            <p>If you did not register for an account, please ignore this email.</p>
        </div>
        <div class="footer">
            <p>&copy; {{ year }} Auth API. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
        """
        )

# Create password reset email template if it doesn't exist
reset_template_path = email_templates_path / "password_reset.html"
if not reset_template_path.exists():
    with open(reset_template_path, "w") as f:
        f.write(
            """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Password Reset</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background-color: #4a69bd; color: white; padding: 10px; text-align: center; }
        .content { padding: 20px; border: 1px solid #ddd; }
        .button { display: inline-block; background-color: #4a69bd; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; }
        .footer { margin-top: 20px; font-size: 12px; color: #777; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Password Reset</h1>
        </div>
        <div class="content">
            <p>Hello {{ username }},</p>
            <p>We received a request to reset your password. Please click the button below to reset your password:</p>
            <p style="text-align: center;">
                <a href="{{ reset_url }}" class="button">Reset Password</a>
            </p>
            <p>Or copy and paste the following URL into your browser:</p>
            <p>{{ reset_url }}</p>
            <p>This link will expire in 1 hour.</p>
            <p>If you did not request a password reset, please ignore this email.</p>
        </div>
        <div class="footer">
            <p>&copy; {{ year }} Auth API. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
        """
        )

# Create Jinja2 environment
env = Environment(
    loader=PackageLoader("app", "templates/email"),
    autoescape=select_autoescape(["html", "xml"]),
)


async def send_email(to_email: str, subject: str, html_content: str):
    """
    Send an email using SMTP
    """
    # Create message
    message = MIMEMultipart()
    message["From"] = settings.EMAIL_FROM
    message["To"] = to_email
    message["Subject"] = subject

    # Attach HTML content
    message.attach(MIMEText(html_content, "html"))

    # Send email
    async with SMTP(
        hostname=settings.SMTP_HOST, port=settings.SMTP_PORT, use_tls=True
    ) as smtp:
        await smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        await smtp.send_message(message)


def create_verification_token(db: Session, user: User) -> str:
    """
    Create a verification token for a user
    """
    # Generate a secure token
    token = secrets.token_urlsafe(32)

    # Set expiration date (24 hours)
    expires_at = datetime.utcnow() + timedelta(hours=24)

    # Create verification token in database
    db_token = VerificationToken(token=token, expires_at=expires_at, user_id=user.id)

    db.add(db_token)
    db.commit()
    db.refresh(db_token)

    return token


def create_password_reset_token(db: Session, user: User) -> str:
    """
    Create a password reset token for a user
    """
    # Generate a secure token
    token = secrets.token_urlsafe(32)

    # Set expiration date (1 hour)
    expires_at = datetime.utcnow() + timedelta(hours=1)

    # Create password reset token in database
    db_token = PasswordResetToken(token=token, expires_at=expires_at, user_id=user.id)

    db.add(db_token)
    db.commit()
    db.refresh(db_token)

    return token


async def send_verification_email(db: Session, user: User, base_url: str):
    """
    Send a verification email to a user
    """
    # Create verification token
    token = create_verification_token(db, user)

    # Create verification URL
    verification_url = f"{base_url}/verify-email?token={token}"

    # Render email template
    template = env.get_template("verification.html")
    html_content = template.render(
        username=user.username,
        verification_url=verification_url,
        year=datetime.now().year,
    )

    # Send email
    await send_email(
        to_email=user.email, subject="Verify Your Email", html_content=html_content
    )


async def send_password_reset_email(db: Session, user: User, base_url: str):
    """
    Send a password reset email to a user
    """
    # Create password reset token
    token = create_password_reset_token(db, user)

    # Create reset URL
    reset_url = f"{base_url}/reset-password?token={token}"

    # Render email template
    template = env.get_template("password_reset.html")
    html_content = template.render(
        username=user.username, reset_url=reset_url, year=datetime.now().year
    )

    # Send email
    await send_email(
        to_email=user.email, subject="Reset Your Password", html_content=html_content
    )
