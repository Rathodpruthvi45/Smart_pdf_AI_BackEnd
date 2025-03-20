from datetime import datetime, timedelta
from typing import Optional, Union, Any
from jose import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Cookie
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import uuid
import secrets

from ..db.database import get_db
from ..models.user import User, RefreshToken
from ..core.config import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a password
    """
    return pwd_context.hash(password)


def create_access_token(
    subject: Union[str, Any], role: str, expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    # Create JWT ID for token revocation
    jti = str(uuid.uuid4())

    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "role": role,
        "jti": jti,
        "type": "access",
    }

    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )

    return encoded_jwt


def create_refresh_token(
    db: Session,
    user_id: int,
    user_agent: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> str:
    """
    Create a refresh token and store it in the database
    """
    # Generate a secure token
    token = secrets.token_urlsafe(64)

    # Set expiration date
    expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    expires_at = datetime.utcnow() + expires_delta

    # Create refresh token in database
    db_refresh_token = RefreshToken(
        token=token,
        expires_at=expires_at,
        user_id=user_id,
        user_agent=user_agent,
        ip_address=ip_address,
    )

    db.add(db_refresh_token)
    db.commit()
    db.refresh(db_refresh_token)

    return token


def generate_csrf_token() -> str:
    """
    Generate a CSRF token
    """
    return secrets.token_urlsafe(32)


def verify_csrf_token(csrf_token: str, csrf_cookie: str) -> bool:
    """
    Verify a CSRF token against the cookie using constant time comparison
    to prevent timing attacks. Both tokens must be non-empty and match exactly.
    """
    if not csrf_token or not csrf_cookie:
        return False

    try:
        return secrets.compare_digest(csrf_token, csrf_cookie)
    except Exception:
        return False


async def get_current_user(
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme),
    access_token: Optional[str] = Cookie(None),
) -> User:
    """
    Get the current user from the access token
    """
    # Use token from cookie if not provided in header

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(
            access_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )

        # Check if token is an access token
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Get user from database
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Inactive user",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return user

    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_active_verified_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get the current active and verified user
    """
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified",
        )

    return current_user


def is_admin(user: "User") -> bool:
    """Check if the user has admin privileges."""
    # For simplicity, we'll consider a user an admin if they have an admin field set to True
    # or if their email contains 'admin'
    if hasattr(user, "is_admin") and user.is_admin:
        return True

    # Fallback for demonstration - in production, use a proper role-based system
    if hasattr(user, "email") and "admin" in user.email.lower():
        return True

    return False
