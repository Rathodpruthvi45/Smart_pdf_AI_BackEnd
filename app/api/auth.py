from fastapi import APIRouter, Depends, HTTPException, status, Response, Request, Cookie
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional

from ..db.database import get_db
from ..db.redis import get_redis
from ..models.user import User
from ..schemas.user import (
    UserCreate,
    UserResponse,
    Token,
    UserLogin,
    PasswordResetRequest,
    PasswordReset,
    EmailVerification,
)
from ..services.user import (
    create_user,
    get_user_by_email,
    get_user_by_username,
    authenticate_user,
    verify_user_email,
    reset_user_password,
    get_refresh_token,
    revoke_refresh_token,
    revoke_all_user_refresh_tokens,
)
from ..services.email import send_verification_email, send_password_reset_email
from ..core.security import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    generate_csrf_token,
    verify_csrf_token,
)
from ..core.config import settings
from ..core.rate_limiter import (
    login_rate_limiter,
    registration_rate_limiter,
    password_reset_rate_limiter,
    get_client_ip,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    request: Request,
    user_create: UserCreate,
    db: Session = Depends(get_db),
  
):
    """
    Register a new user
    """
    # Check if email already exists
    if get_user_by_email(db, user_create.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Check if username already exists
    if get_user_by_username(db, user_create.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken"
        )

    # Create the user
    user = create_user(db, user_create)

    # Send verification email
    base_url = str(request.base_url)
    try:
        await send_verification_email(db, user, base_url)
    except Exception as e:
        # Log the error but don't fail registration
        print(f"Error sending verification email: {e}")

    return user


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
   
):
    """
    Login a user and return an access token
    """
    # Authenticate the user
    user = authenticate_user(db, form_data.username, form_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.id, role=user.role, expires_delta=access_token_expires
    )

    # Create refresh token
    refresh_token = create_refresh_token(
        db=db,
        user_id=user.id,
        user_agent=request.headers.get("User-Agent"),
        ip_address=get_client_ip(request),
    )

    # Generate CSRF token
    csrf_token = generate_csrf_token()

    # Set cookies
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,  # Set to False in development
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,  # Set to False in development
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/",
    )

    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,  # Must be accessible from JavaScript
        secure=True,  # Set to False in development
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post("/login/json", response_model=Token)
async def login_json(
    request: Request,
    response: Response,
    user_login: UserLogin,
    db: Session = Depends(get_db),
   
):
    """
    Login a user with JSON and return an access token
    """
    # Authenticate the user
    user = authenticate_user(db, user_login.email, user_login.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.id, role=user.role, expires_delta=access_token_expires
    )

    # Create refresh token
    refresh_token = create_refresh_token(
        db=db,
        user_id=user.id,
        user_agent=request.headers.get("User-Agent"),
        ip_address=get_client_ip(request),
    )

    # Generate CSRF token
    csrf_token = generate_csrf_token()

    # Set cookies
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,  # Set to False in development
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,  # Set to False in development
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/",
    )

    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,  # Must be accessible from JavaScript
        secure=True,  # Set to False in development
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: Request,
    response: Response,
    refresh_token: Optional[str] = Cookie(None),
    csrf_token: Optional[str] = Cookie(None),
    x_csrf_token: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Refresh an access token
    """
    # Check if refresh token exists
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if CSRF token exists
    if not csrf_token or not x_csrf_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="CSRF token missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify CSRF token
    if not verify_csrf_token(x_csrf_token, csrf_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid CSRF token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get the refresh token from the database
    db_refresh_token = get_refresh_token(db, refresh_token)

    if not db_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get the user
    user = db.query(User).filter(User.id == db_refresh_token.user_id).first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create a new access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.id, role=user.role, expires_delta=access_token_expires
    )

    # Generate a new CSRF token
    new_csrf_token = generate_csrf_token()

    # Set cookies
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,  # Set to False in development
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )

    response.set_cookie(
        key="csrf_token",
        value=new_csrf_token,
        httponly=False,  # Must be accessible from JavaScript
        secure=True,  # Set to False in development
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post("/logout")
async def logout(
    response: Response,
    refresh_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db),
):
    """
    Logout a user
    """
    # Revoke the refresh token if it exists
    if refresh_token:
        revoke_refresh_token(db, refresh_token)

    # Clear cookies
    response.delete_cookie(key="access_token", path="/")

    response.delete_cookie(key="refresh_token", path="/")

    response.delete_cookie(key="csrf_token", path="/")

    return {"detail": "Successfully logged out"}


@router.post("/verify-email")
async def verify_email(verification: EmailVerification, db: Session = Depends(get_db)):
    """
    Verify a user's email
    """
    user = verify_user_email(db, verification.token)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    return {"detail": "Email successfully verified"}


@router.post("/request-password-reset")
async def request_password_reset(
    request: Request,
    password_reset: PasswordResetRequest,
    db: Session = Depends(get_db),
    _: None = Depends(password_reset_rate_limiter),
):
    """
    Request a password reset
    """
    # Get the user by email
    user = get_user_by_email(db, password_reset.email)

    # If user exists, send password reset email
    if user:
        base_url = str(request.base_url)
        try:
            await send_password_reset_email(db, user, base_url)
        except Exception as e:
            # Log the error but don't expose user existence
            print(f"Error sending password reset email: {e}")

    # Always return success to prevent user enumeration
    return {
        "detail": "If your email is registered, you will receive a password reset link"
    }


@router.post("/reset-password")
async def reset_password(password_reset: PasswordReset, db: Session = Depends(get_db)):
    """
    Reset a user's password
    """
    user = reset_user_password(db, password_reset.token, password_reset.new_password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token",
        )

    # Revoke all refresh tokens for the user
    revoke_all_user_refresh_tokens(db, user.id)

    return {"detail": "Password successfully reset"}
