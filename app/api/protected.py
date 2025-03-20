from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any

from ..models.user import User, UserRole
from ..core.security import get_current_user, get_current_active_verified_user
from ..core.rbac import allow_admin, allow_moderator, allow_all_users

router = APIRouter(prefix="/protected", tags=["protected"])


@router.get("/public")
async def public_route():
    """
    Public route that doesn't require authentication
    """
    return {"message": "This is a public route", "access": "public"}


@router.get("/authenticated")
async def authenticated_route(current_user: User = Depends(get_current_user)):
    """
    Protected route that requires authentication
    """
    return {
        "message": "This is a protected route",
        "access": "authenticated",
        "user_id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
    }


@router.get("/verified")
async def verified_route(
    current_user: User = Depends(get_current_active_verified_user),
):
    """
    Protected route that requires a verified user
    """
    return {
        "message": "This is a verified route",
        "access": "verified",
        "user_id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
    }


@router.get("/user")
async def user_route(current_user: User = Depends(allow_all_users)):
    """
    Protected route that requires a user role
    """
    return {
        "message": "This is a user route",
        "access": "user",
        "user_id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
    }


@router.get("/moderator")
async def moderator_route(current_user: User = Depends(allow_moderator)):
    """
    Protected route that requires a moderator role
    """
    return {
        "message": "This is a moderator route",
        "access": "moderator",
        "user_id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
    }


@router.get("/admin")
async def admin_route(current_user: User = Depends(allow_admin)):
    """
    Protected route that requires an admin role
    """
    return {
        "message": "This is an admin route",
        "access": "admin",
        "user_id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
    }
