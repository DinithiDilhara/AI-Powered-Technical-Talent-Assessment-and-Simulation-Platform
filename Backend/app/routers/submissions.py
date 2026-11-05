import json

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.database import get_connection
from app.dependencies import require_role
from app.schemas import (
    SubmissionAnswersUpdate,
    SubmissionResponse,
    SubmissionStart,
)


router = APIRouter(prefix="/submissions", tags=["Submissions"])
SUBMISSION_COLUMNS = (
    "s.id, s.candidate_id, s.assessment_id, s.answers, s.score, "
    "s.status, s.started_at, s.submitted_at"
)


def _as_submission(row):
    return dict(zip(
        ("id", "candidate_id", "assessment_id", "answers", "score", "status", "started_at", "submitted_at"),
        row,
    ))


def _owned_submission_query(suffix=""):
    return (
        f"SELECT {SUBMISSION_COLUMNS} FROM submissions s "
        "JOIN candidates c ON c.id = s.candidate_id "
        f"WHERE c.user_id = %s {suffix}"
    )


@router.post("", response_model=SubmissionResponse, status_code=status.HTTP_201_CREATED)
def start_submission(
    data: SubmissionStart,
    response: Response,
    current_user: dict = Depends(require_role("candidate")),
):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM candidates WHERE user_id = %s",
                (current_user["id"],),
            )
            candidate = cursor.fetchone()
            if candidate is None:
                raise HTTPException(status_code=404, detail="Candidate profile not found")
            candidate_id = candidate[0]

            # Resume before checking assessment availability: closing an assessment
            # prevents new attempts but does not invalidate an existing attempt.
            cursor.execute(
                f"SELECT {SUBMISSION_COLUMNS} FROM submissions s "
                "WHERE s.candidate_id = %s AND s.assessment_id = %s",
                (candidate_id, data.assessment_id),
            )
            existing = cursor.fetchone()
            if existing is not None:
                if existing[5] == "in_progress":
                    response.status_code = status.HTTP_200_OK
                    connection.commit()
                    return _as_submission(existing)
                raise HTTPException(
                    status_code=409,
                    detail="A submission for this assessment has already been completed",
                )

            # Lock the assessment row during the insert so it cannot be closed
            # between availability validation and creation of the attempt.
            cursor.execute(
                "SELECT status FROM assessments WHERE id = %s FOR SHARE",
                (data.assessment_id,),
            )
            assessment = cursor.fetchone()
            if assessment is None:
                raise HTTPException(status_code=404, detail="Assessment not found")
            if assessment[0] != "published":
                # A concurrent start may have completed after the first
                # existing-submission lookup. Honor resume semantics even if
                # the assessment was closed before this request acquired its
                # assessment-row lock.
                cursor.execute(
                    f"SELECT {SUBMISSION_COLUMNS} FROM submissions s "
                    "WHERE s.candidate_id = %s AND s.assessment_id = %s",
                    (candidate_id, data.assessment_id),
                )
                concurrent = cursor.fetchone()
                if concurrent is not None and concurrent[5] == "in_progress":
                    response.status_code = status.HTTP_200_OK
                    connection.commit()
                    return _as_submission(concurrent)
                raise HTTPException(status_code=409, detail="Only published assessments can be started")

            cursor.execute(
                f"""INSERT INTO submissions (candidate_id, assessment_id, answers, status)
                    VALUES (%s, %s, '{{}}'::jsonb, 'in_progress')
                    ON CONFLICT (candidate_id, assessment_id) DO NOTHING
                    RETURNING {SUBMISSION_COLUMNS}""",
                (candidate_id, data.assessment_id),
            )
            created = cursor.fetchone()
            if created is None:
                # Another request won the unique-key race. A new statement sees
                # its committed row after ON CONFLICT has waited for that insert.
                cursor.execute(
                    f"SELECT {SUBMISSION_COLUMNS} FROM submissions s "
                    "WHERE s.candidate_id = %s AND s.assessment_id = %s",
                    (candidate_id, data.assessment_id),
                )
                created = cursor.fetchone()
                if created is None:
                    raise HTTPException(status_code=409, detail="Could not start assessment; retry the request")
                if created[5] != "in_progress":
                    raise HTTPException(status_code=409, detail="A submission for this assessment has already been completed")
                response.status_code = status.HTTP_200_OK

        connection.commit()
        return _as_submission(created)
    except HTTPException:
        connection.rollback()
        raise
    except Exception:
        connection.rollback()
        raise HTTPException(status_code=500, detail="Could not start submission")
    finally:
        connection.close()


@router.get("/me", response_model=list[SubmissionResponse])
def list_my_submissions(current_user: dict = Depends(require_role("candidate"))):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                _owned_submission_query("ORDER BY s.started_at DESC, s.id DESC"),
                (current_user["id"],),
            )
            rows = cursor.fetchall()
        return [_as_submission(row) for row in rows]
    except Exception:
        raise HTTPException(status_code=500, detail="Could not retrieve submissions")
    finally:
        connection.close()


@router.get("/{submission_id}", response_model=SubmissionResponse)
def get_submission(submission_id: int, current_user: dict = Depends(require_role("candidate"))):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                _owned_submission_query("AND s.id = %s"),
                (current_user["id"], submission_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Submission not found")
        return _as_submission(row)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Could not retrieve submission")
    finally:
        connection.close()


@router.patch("/{submission_id}/answers", response_model=SubmissionResponse)
def save_submission_answers(
    submission_id: int,
    data: SubmissionAnswersUpdate,
    current_user: dict = Depends(require_role("candidate")),
):
    connection = get_connection()
    try:
        encoded_answers = json.dumps(data.answers, allow_nan=False)
        with connection.cursor() as cursor:
            cursor.execute(
                f"""UPDATE submissions s
                    SET answers = COALESCE(s.answers, '{{}}'::jsonb) || %s::jsonb
                    FROM candidates c
                    WHERE s.id = %s AND s.candidate_id = c.id AND c.user_id = %s
                      AND s.status = 'in_progress'
                    RETURNING {SUBMISSION_COLUMNS}""",
                (encoded_answers, submission_id, current_user["id"]),
            )
            row = cursor.fetchone()
            if row is None:
                cursor.execute(
                    _owned_submission_query("AND s.id = %s"),
                    (current_user["id"], submission_id),
                )
                existing = cursor.fetchone()
                if existing is None:
                    raise HTTPException(status_code=404, detail="Submission not found")
                raise HTTPException(status_code=409, detail="Only in-progress submissions can be edited")
        connection.commit()
        return _as_submission(row)
    except HTTPException:
        connection.rollback()
        raise
    except Exception:
        connection.rollback()
        raise HTTPException(status_code=500, detail="Could not save submission answers")
    finally:
        connection.close()


@router.post("/{submission_id}/submit", response_model=SubmissionResponse)
def submit_submission(submission_id: int, current_user: dict = Depends(require_role("candidate"))):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""UPDATE submissions s
                    SET status = 'submitted', submitted_at = CURRENT_TIMESTAMP
                    FROM candidates c
                    WHERE s.id = %s AND s.candidate_id = c.id AND c.user_id = %s
                      AND s.status = 'in_progress'
                    RETURNING {SUBMISSION_COLUMNS}""",
                (submission_id, current_user["id"]),
            )
            row = cursor.fetchone()
            if row is None:
                cursor.execute(
                    _owned_submission_query("AND s.id = %s"),
                    (current_user["id"], submission_id),
                )
                existing = cursor.fetchone()
                if existing is None:
                    raise HTTPException(status_code=404, detail="Submission not found")
                raise HTTPException(status_code=409, detail="Only in-progress submissions can be submitted")
        connection.commit()
        return _as_submission(row)
    except HTTPException:
        connection.rollback()
        raise
    except Exception:
        connection.rollback()
        raise HTTPException(status_code=500, detail="Could not submit answers")
    finally:
        connection.close()
