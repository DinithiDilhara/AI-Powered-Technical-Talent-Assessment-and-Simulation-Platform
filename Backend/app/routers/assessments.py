from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_connection
from app.dependencies import require_role
from app.schemas import AssessmentCreate, AssessmentResponse, AssessmentUpdate


router = APIRouter(prefix="/assessments", tags=["Assessments"])
ASSESSMENT_COLUMNS = (
    "id, title, description, technical_role, difficulty, duration, "
    "created_by, status, created_at"
)
UPDATE_COLUMNS = {
    "title": "title",
    "description": "description",
    "technical_role": "technical_role",
    "difficulty": "difficulty",
    "duration": "duration",
}


def _as_assessment(row):
    return dict(zip(
        (
            "id", "title", "description", "technical_role", "difficulty",
            "duration", "created_by", "status", "created_at",
        ),
        row,
    ))


@router.post("", response_model=AssessmentResponse, status_code=status.HTTP_201_CREATED)
def create_assessment(
    assessment: AssessmentCreate,
    current_user: dict = Depends(require_role("employer")),
):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""INSERT INTO assessments
                       (title, description, technical_role, difficulty, duration, created_by, status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'draft')
                    RETURNING {ASSESSMENT_COLUMNS}""",
                (
                    assessment.title,
                    assessment.description,
                    assessment.technical_role.value if assessment.technical_role else None,
                    assessment.difficulty.value,
                    assessment.duration,
                    current_user["id"],
                ),
            )
            row = cursor.fetchone()
        connection.commit()
        return _as_assessment(row)
    except Exception:
        connection.rollback()
        raise HTTPException(status_code=500, detail="Could not create assessment")
    finally:
        connection.close()


@router.get("", response_model=list[AssessmentResponse])
def list_my_assessments(current_user: dict = Depends(require_role("employer"))):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {ASSESSMENT_COLUMNS} FROM assessments WHERE created_by = %s ORDER BY created_at DESC, id DESC",
                (current_user["id"],),
            )
            rows = cursor.fetchall()
        return [_as_assessment(row) for row in rows]
    except Exception:
        raise HTTPException(status_code=500, detail="Could not retrieve assessments")
    finally:
        connection.close()


@router.get("/published", response_model=list[AssessmentResponse])
def list_published_assessments(current_user: dict = Depends(require_role("candidate"))):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {ASSESSMENT_COLUMNS} FROM assessments WHERE status = 'published' ORDER BY created_at DESC, id DESC",
                (),
            )
            rows = cursor.fetchall()
        return [_as_assessment(row) for row in rows]
    except Exception:
        raise HTTPException(status_code=500, detail="Could not retrieve published assessments")
    finally:
        connection.close()


@router.get("/{assessment_id}", response_model=AssessmentResponse)
def get_assessment(assessment_id: int, current_user: dict = Depends(require_role("employer"))):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {ASSESSMENT_COLUMNS} FROM assessments WHERE id = %s AND created_by = %s",
                (assessment_id, current_user["id"]),
            )
            row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Assessment not found")
        return _as_assessment(row)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Could not retrieve assessment")
    finally:
        connection.close()


@router.patch("/{assessment_id}", response_model=AssessmentResponse)
def update_assessment(
    assessment_id: int,
    updates: AssessmentUpdate,
    current_user: dict = Depends(require_role("employer")),
):
    values = updates.model_dump(exclude_unset=True)
    for key, value in values.items():
        if value is not None and key in ("technical_role", "difficulty"):
            values[key] = value.value
    assignments = ", ".join(f"{UPDATE_COLUMNS[key]} = %s" for key in values)
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT status FROM assessments WHERE id = %s AND created_by = %s",
                (assessment_id, current_user["id"]),
            )
            owned = cursor.fetchone()
            if owned is None:
                raise HTTPException(status_code=404, detail="Assessment not found")
            if owned[0] != "draft":
                raise HTTPException(status_code=409, detail="Only draft assessments can be edited")
            cursor.execute(
                f"UPDATE assessments SET {assignments} WHERE id = %s AND created_by = %s AND status = 'draft' RETURNING {ASSESSMENT_COLUMNS}",
                (*values.values(), assessment_id, current_user["id"]),
            )
            row = cursor.fetchone()
        if row is None:
            connection.rollback()
            raise HTTPException(status_code=409, detail="Assessment status changed; reload and try again")
        connection.commit()
        return _as_assessment(row)
    except HTTPException:
        connection.rollback()
        raise
    except Exception:
        connection.rollback()
        raise HTTPException(status_code=500, detail="Could not update assessment")
    finally:
        connection.close()


def _transition_assessment(assessment_id: int, employer_id: int, from_status: str, to_status: str):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE assessments SET status = %s WHERE id = %s AND created_by = %s AND status = %s RETURNING {ASSESSMENT_COLUMNS}",
                (to_status, assessment_id, employer_id, from_status),
            )
            row = cursor.fetchone()
            if row is None:
                cursor.execute(
                    "SELECT status FROM assessments WHERE id = %s AND created_by = %s",
                    (assessment_id, employer_id),
                )
                existing = cursor.fetchone()
                if existing is None:
                    raise HTTPException(status_code=404, detail="Assessment not found")
                raise HTTPException(
                    status_code=409,
                    detail=f"Assessment must be {from_status} to transition to {to_status}",
                )
        connection.commit()
        return _as_assessment(row)
    except HTTPException:
        connection.rollback()
        raise
    except Exception:
        connection.rollback()
        raise HTTPException(status_code=500, detail="Could not change assessment status")
    finally:
        connection.close()


@router.post("/{assessment_id}/publish", response_model=AssessmentResponse)
def publish_assessment(assessment_id: int, current_user: dict = Depends(require_role("employer"))):
    return _transition_assessment(assessment_id, current_user["id"], "draft", "published")


@router.post("/{assessment_id}/close", response_model=AssessmentResponse)
def close_assessment(assessment_id: int, current_user: dict = Depends(require_role("employer"))):
    return _transition_assessment(assessment_id, current_user["id"], "published", "closed")
