from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional

class UserBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=50, pattern=r"^[a-zA-Z\s]+$")
    age: int = Field(..., ge=18, le=100)
    gender: str = Field(..., pattern=r"^(male|female|other)$")
    email: EmailStr  # Enforces valid email format
    city: str = Field(..., pattern=r"^[a-zA-Z\s]+$")
    interests: List[str] 

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    email: Optional[EmailStr] = None
    city: Optional[str] = None
    interests: Optional[List[str]] = None


class User(UserBase):
    id: int

    class Config:
        from_attributes = True

