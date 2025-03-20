from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from ..db.database import get_db
from ..models.user import User, UserRole
from ..schemas.user import UserResponse, UserUpdate, PasswordChange
from ..services.user import (
    get_user_by_id,
    get_users,
    update_user,
    change_user_password,
    update_user_role,
)
from ..core.security import get_current_user, verify_password
from ..core.rbac import allow_admin, allow_moderator, allow_all_users

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get the current user's information
    """
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update the current user's information
    """
    return update_user(db, current_user, user_update)


@router.post("/me/change-password")
async def change_current_user_password(
    password_change: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Change the current user's password
    """
    # Verify current password
    if not verify_password(
        password_change.current_password, current_user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect current password"
        )

    # Change password
    change_user_password(db, current_user, password_change.new_password)

    return {"detail": "Password successfully changed"}


@router.get("", response_model=List[UserResponse])
async def get_all_users(
    skip: int = 0,
    limit: int = 100,
    role: UserRole = None,
    current_user: User = Depends(allow_admin),
):
    """
    Get all users (admin only)
    """
    db = next(get_db())
    return get_users(db, skip=skip, limit=limit, role=role)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, current_user: User = Depends(allow_moderator)):
    """
    Get a user by ID (admin and moderator only)
    """
    db = next(get_db())
    user = get_user_by_id(db, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    return user


@router.put("/{user_id}/role")
async def update_user_role_endpoint(
    user_id: int,
    role: UserRole,
    current_user: User = Depends(allow_admin),
    db: Session = Depends(get_db),
):
    """
    Update a user's role (admin only)
    """
    # Get the user
    user = get_user_by_id(db, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Prevent changing own role
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change own role"
        )

    # Update the user's role
    update_user_role(db, user, role)

    return {"detail": f"User role updated to {role}"}
