
from enum import Enum
from pydantic import BaseModel, EmailStr, Field


class UserRole(str, Enum):
    employer = "employer"
    candidate = "candidate"


class UserRegister(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    # Public registration is candidate-only. The endpoint rejects explicit
    # employer requests; omission remains compatible with simpler clients.
    role: UserRole = UserRole.candidate

class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
