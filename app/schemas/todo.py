from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# Base Todo Schema
class TodoBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    completed: bool = False


# Todo Create Schema
class TodoCreate(TodoBase):
    pass


# Todo Update Schema
class TodoUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    completed: Optional[bool] = None


# Todo Response Schema
class TodoResponse(TodoBase):
    id: int
    user_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
