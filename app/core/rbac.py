from fastapi import Depends, HTTPException, status
from typing import List, Optional
from ..models.user import User, UserRole
from .security import get_current_user


class RoleChecker:
    def __init__(self, allowed_roles: List[UserRole]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: User = Depends(get_current_user)) -> User:
        if user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role {user.role} not authorized to access this resource",
            )
        return user


# Role-based dependencies
allow_admin = RoleChecker([UserRole.ADMIN])
allow_moderator = RoleChecker([UserRole.ADMIN, UserRole.MODERATOR])
allow_all_users = RoleChecker([UserRole.ADMIN, UserRole.MODERATOR, UserRole.USER])
