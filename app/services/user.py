from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime
from typing import Optional, List, Dict, Any

from ..models.user import (
    User,
    RefreshToken,
    VerificationToken,
    PasswordResetToken,
    UserRole,
)
from ..schemas.user import UserCreate, UserUpdate
from ..core.security import get_password_hash, verify_password


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """
    Get a user by ID
    """
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """
    Get a user by email
    """
    return db.query(User).filter(User.email == email).first()


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """
    Get a user by username
    """
    return db.query(User).filter(User.username == username).first()


def get_users(
    db: Session, skip: int = 0, limit: int = 100, role: Optional[UserRole] = None
) -> List[User]:
    """
    Get a list of users with optional filtering by role
    """
    query = db.query(User)

    if role:
        query = query.filter(User.role == role)

    return query.offset(skip).limit(limit).all()


def create_user(db: Session, user_create: UserCreate) -> User:
    """
    Create a new user
    """
    # Hash the password
    hashed_password = get_password_hash(user_create.password)

    # Create the user
    db_user = User(
        email=user_create.email,
        username=user_create.username,
        hashed_password=hashed_password,
        full_name=user_create.full_name,
        is_active=True,  # Set to False if email verification is required
        is_verified=False,
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user


def update_user(db: Session, user: User, user_update: UserUpdate) -> User:
    """
    Update a user
    """
    # Update user fields
    update_data = user_update.dict(exclude_unset=True)

    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)

    return user


def change_user_password(db: Session, user: User, new_password: str) -> User:
    """
    Change a user's password
    """
    # Hash the new password
    hashed_password = get_password_hash(new_password)

    # Update the user's password
    user.hashed_password = hashed_password

    db.commit()
    db.refresh(user)

    return user


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """
    Authenticate a user
    """
    # Get the user by email
    user = get_user_by_email(db, email)

    # Check if user exists and password is correct
    if not user or not verify_password(password, user.hashed_password):
        return None

    return user


def verify_user_email(db: Session, token: str) -> Optional[User]:
    """
    Verify a user's email
    """
    # Get the verification token
    db_token = (
        db.query(VerificationToken)
        .filter(
            VerificationToken.token == token,
            VerificationToken.expires_at > datetime.utcnow(),
        )
        .first()
    )

    if not db_token:
        return None

    # Get the user
    user = get_user_by_id(db, db_token.user_id)

    if not user:
        return None

    # Update the user
    user.is_verified = True

    # Delete the token
    db.delete(db_token)

    db.commit()
    db.refresh(user)

    return user


def reset_user_password(db: Session, token: str, new_password: str) -> Optional[User]:
    """
    Reset a user's password
    """
    # Get the password reset token
    db_token = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token == token,
            PasswordResetToken.expires_at > datetime.utcnow(),
        )
        .first()
    )

    if not db_token:
        return None

    # Get the user
    user = get_user_by_id(db, db_token.user_id)

    if not user:
        return None

    # Update the user's password
    user.hashed_password = get_password_hash(new_password)

    # Delete the token
    db.delete(db_token)

    db.commit()
    db.refresh(user)

    return user


def get_refresh_token(db: Session, token: str) -> Optional[RefreshToken]:
    """
    Get a refresh token
    """
    return (
        db.query(RefreshToken)
        .filter(
            RefreshToken.token == token,
            RefreshToken.expires_at > datetime.utcnow(),
            RefreshToken.revoked == False,
        )
        .first()
    )


def revoke_refresh_token(db: Session, token: str) -> bool:
    """
    Revoke a refresh token
    """
    # Get the refresh token
    db_token = db.query(RefreshToken).filter(RefreshToken.token == token).first()

    if not db_token:
        return False

    # Revoke the token
    db_token.revoked = True

    db.commit()

    return True


def revoke_all_user_refresh_tokens(db: Session, user_id: int) -> bool:
    """
    Revoke all refresh tokens for a user
    """
    # Get all refresh tokens for the user
    db_tokens = (
        db.query(RefreshToken)
        .filter(RefreshToken.user_id == user_id, RefreshToken.revoked == False)
        .all()
    )

    if not db_tokens:
        return False

    # Revoke all tokens
    for token in db_tokens:
        token.revoked = True

    db.commit()

    return True


def update_user_role(db: Session, user: User, role: UserRole) -> User:
    """
    Update a user's role
    """
    # Update the user's role
    user.role = role

    db.commit()
    db.refresh(user)

    return user
