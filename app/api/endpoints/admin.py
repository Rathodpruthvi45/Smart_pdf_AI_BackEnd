from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
import os
import glob
import shutil
from ...core.security import get_current_user, is_admin
from ...models.user import User

router = APIRouter()


# Models
class UserStats(BaseModel):
    id: str
    email: str
    created_at: datetime
    subscription_tier: str
    pdf_count: int
    question_count: int
    is_active: bool


class PdfInfo(BaseModel):
    id: str
    filename: str
    user_id: str
    user_email: str
    created_at: datetime
    size_kb: float


class DashboardStats(BaseModel):
    total_users: int
    active_users: int
    total_pdfs: int
    total_questions_generated: int
    users_by_tier: dict
    recent_activity: List[dict]


# Admin endpoints
@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(current_user: User = Depends(get_current_user)):
    """Get overall statistics for the admin dashboard"""
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")

    # This would normally come from a database query
    # Mocking data for demonstration
    return {
        "total_users": 156,
        "active_users": 89,
        "total_pdfs": 342,
        "total_questions_generated": 2589,
        "users_by_tier": {"free": 98, "pro": 45, "enterprise": 13},
        "recent_activity": [
            {
                "type": "pdf_upload",
                "user_id": "user123",
                "user_email": "user@example.com",
                "timestamp": datetime.now() - timedelta(hours=2),
                "details": "uploaded physics_textbook.pdf",
            },
            {
                "type": "question_generation",
                "user_id": "user456",
                "user_email": "another@example.com",
                "timestamp": datetime.now() - timedelta(hours=5),
                "details": "generated 10 questions",
            },
        ],
    }


@router.get("/users", response_model=List[UserStats])
async def get_all_users(
    current_user: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = None,
):
    """Get all users with pagination and search"""
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")

    # Mock data for demonstration
    users = [
        {
            "id": "u1",
            "email": "user1@example.com",
            "created_at": datetime.now() - timedelta(days=30),
            "subscription_tier": "free",
            "pdf_count": 3,
            "question_count": 25,
            "is_active": True,
        },
        {
            "id": "u2",
            "email": "user2@example.com",
            "created_at": datetime.now() - timedelta(days=15),
            "subscription_tier": "pro",
            "pdf_count": 8,
            "question_count": 120,
            "is_active": True,
        },
        {
            "id": "u3",
            "email": "admin@example.com",
            "created_at": datetime.now() - timedelta(days=60),
            "subscription_tier": "enterprise",
            "pdf_count": 15,
            "question_count": 300,
            "is_active": True,
        },
    ]

    # Filter by search term if provided
    if search:
        users = [u for u in users if search.lower() in u["email"].lower()]

    # Apply pagination
    return users[skip : skip + limit]


@router.get("/pdfs", response_model=List[PdfInfo])
async def get_all_pdfs(
    current_user: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    user_id: Optional[str] = None,
):
    """Get all PDFs with pagination and filtering by user"""
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")

    # Mock data for demonstration
    pdfs = [
        {
            "id": "pdf_u1_physics.pdf",
            "filename": "physics.pdf",
            "user_id": "u1",
            "user_email": "user1@example.com",
            "created_at": datetime.now() - timedelta(days=20),
            "size_kb": 1240.5,
        },
        {
            "id": "pdf_u2_chemistry.pdf",
            "filename": "chemistry.pdf",
            "user_id": "u2",
            "user_email": "user2@example.com",
            "created_at": datetime.now() - timedelta(days=10),
            "size_kb": 2350.8,
        },
        {
            "id": "pdf_u3_math.pdf",
            "filename": "math.pdf",
            "user_id": "u3",
            "user_email": "admin@example.com",
            "created_at": datetime.now() - timedelta(days=5),
            "size_kb": 1845.2,
        },
    ]

    # Filter by user_id if provided
    if user_id:
        pdfs = [p for p in pdfs if p["user_id"] == user_id]

    # Apply pagination
    return pdfs[skip : skip + limit]


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, current_user: User = Depends(get_current_user)):
    """Delete a user and all their associated data"""
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")

    # In a real implementation:
    # 1. Delete user from database
    # 2. Delete all user's PDFs
    # 3. Delete vectorstores

    # For mock implementation, just return success
    return {"status": "success", "message": f"User {user_id} deleted successfully"}


@router.delete("/pdfs/{pdf_id}")
async def delete_pdf(pdf_id: str, current_user: User = Depends(get_current_user)):
    """Delete a specific PDF and its vectorstore"""
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")

    # Check if vectorstore exists
    vectorstore_path = f"vectorstores/{pdf_id}"
    if not os.path.exists(vectorstore_path):
        raise HTTPException(status_code=404, detail=f"PDF with ID {pdf_id} not found")

    # In a real implementation:
    # 1. Delete PDF record from database
    # 2. Delete vectorstore files

    # For demonstration purposes
    return {"status": "success", "message": f"PDF {pdf_id} deleted successfully"}
