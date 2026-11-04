
import os
from datetime import datetime, timedelta, timezone

import jwt
from dotenv import load_dotenv
from pwdlib import PasswordHash
from fastapi import HTTPException

# Load environment variables from the .env file
load_dotenv()

# Password hashing setup
password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


# JWT configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY")

if not SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET_KEY is missing from .env"
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


# Create an access token after successful login
def create_access_token(user_id: int, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": expire
    }

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

def verify_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        user_id = payload.get("sub")
        role = payload.get("role")

        if user_id is None or role not in {"employer", "candidate"}:
            raise ValueError("Invalid token data")

        return payload

    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired access token"
        )
