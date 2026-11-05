
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional

from app.database import get_connection
from app.dependencies import require_role


router = APIRouter(
    prefix="/candidates",
    tags=["Candidates"]
)


class CandidateProfileCreate(BaseModel):
    education: Optional[str] = None
    skills: Optional[str] = None
    experience: Optional[str] = None
    bio: Optional[str] = None


class CandidateProfileResponse(CandidateProfileCreate):
    id: int
    user_id: int


@router.post("/me", status_code=status.HTTP_201_CREATED)
def create_candidate_profile(
    profile: CandidateProfileCreate,
    current_user: dict = Depends(require_role("candidate"))
):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO candidates (
                    user_id, education, skills, experience, bio
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, user_id, education, skills, experience, bio
                """,
                (
                    current_user["id"],
                    profile.education,
                    profile.skills,
                    profile.experience,
                    profile.bio
                )
            )

            result = cursor.fetchone()

        connection.commit()

        return {
            "message": "Candidate profile created successfully",
            "profile": {
                "id": result[0],
                "user_id": result[1],
                "education": result[2],
                "skills": result[3],
                "experience": result[4],
                "bio": result[5]
            }
        }

    except Exception as error:
        connection.rollback()

        if getattr(error, "sqlstate", None) == "23505":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Candidate profile already exists"
            )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create candidate profile"
        )

    finally:
        connection.close()


@router.get("/me")
def get_candidate_profile(
    current_user: dict = Depends(require_role("candidate"))
):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, user_id, education, skills, experience, bio
                FROM candidates
                WHERE user_id = %s
                """,
                (current_user["id"],)
            )

            result = cursor.fetchone()

        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Candidate profile not found"
            )

        return {
            "id": result[0],
            "user_id": result[1],
            "education": result[2],
            "skills": result[3],
            "experience": result[4],
            "bio": result[5]
        }

    finally:
        connection.close()
