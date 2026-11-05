
from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_connection
from app.dependencies import get_current_user
from app.security import verify_password, create_access_token
from app.schemas import UserLogin


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


@router.get("/me")
def get_authenticated_user(current_user: dict = Depends(get_current_user)):
    """Return identity claims only after the bearer token has been verified."""
    return {"id": current_user["id"], "role": current_user["role"]}


@router.post("/login")
def login_user(user: UserLogin):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, full_name, email, password_hash, role
                FROM users
                WHERE email = %s
                """,
                (str(user.email),)
            )

            db_user = cursor.fetchone()

        # Check whether the user exists
        if db_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        # Verify the password
        if not verify_password(user.password, db_user[3]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        # Create an access token
        access_token = create_access_token(
            user_id=db_user[0],
            role=db_user[4]
        )

        # Return the login response
        return {
            "message": "Login successful",
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": db_user[0],
                "full_name": db_user[1],
                "email": db_user[2],
                "role": db_user[4]
            }
        }

    finally:
        connection.close()
