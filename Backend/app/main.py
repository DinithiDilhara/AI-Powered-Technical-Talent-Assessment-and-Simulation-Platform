
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.routers.candidates import router as candidates_router
from app.routers.assessments import router as assessments_router
from app.routers.submissions import router as submissions_router
from app.routers.invitations import router as invitations_router
from app.schemas import UserRegister
from app.security import hash_password
from app.database import get_connection
from app.routers.auth import router as auth_router
from app.dependencies import require_role


app = FastAPI(title="Technical Talent Assessment Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)


app.include_router(auth_router)
app.include_router(candidates_router)
app.include_router(assessments_router)
app.include_router(submissions_router)
app.include_router(invitations_router)


@app.get("/")
def home():
    return {
        "message": "Technical Talent Assessment Platform API is running!"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/db-test")
def test_database():
    connection = get_connection()

    try:
        connection.close()
        return {"message": "Database connection successful!"}

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection failed"
        )


@app.get("/users")
def check_users_table():
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM users")
            result = cursor.fetchone()

        return {
            "users_table": "connected",
            "user_count": result[0]
        }

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve user information"
        )

    finally:
        connection.close()


@app.post("/register", status_code=status.HTTP_201_CREATED)
def register_user(user: UserRegister):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            # Check whether the email already exists
            cursor.execute(
                "SELECT id FROM users WHERE email = %s",
                (str(user.email),)
            )

            existing_user = cursor.fetchone()

            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email is already registered"
                )

            # Hash the password
            hashed_password = hash_password(user.password)

            # Save the new user in PostgreSQL
            cursor.execute(
                """
                INSERT INTO users (
                    full_name, email, password_hash, role
                )
                VALUES (%s, %s, %s, %s)
                RETURNING id, full_name, email, role, created_at
                """,
                (
                    user.full_name,
                    str(user.email),
                    hashed_password,
                    user.role.value
                )
            )

            new_user = cursor.fetchone()

        # Commit the transaction
        connection.commit()

        return {
            "message": "User registered successfully",
            "user": {
                "id": new_user[0],
                "full_name": new_user[1],
                "email": new_user[2],
                "role": new_user[3],
                "created_at": new_user[4]
            }
        }

    except HTTPException:
        connection.rollback()
        raise

    except Exception:
        connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

    finally:
        connection.close()


@app.get("/employer-only")
def employer_only(
    current_user: dict = Depends(require_role("employer"))
):
    return {
        "message": "Welcome, employer!",
        "user": current_user
    }


@app.get("/candidate-only")
def candidate_only(
    current_user: dict = Depends(require_role("candidate"))
):
    return {"message": "Welcome, candidate!", "user": current_user}
