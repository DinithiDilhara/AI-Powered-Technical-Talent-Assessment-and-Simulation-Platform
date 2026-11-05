import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.database import get_connection
from app.dependencies import require_role
from app.routers.submissions import start_submission_for_candidate, _as_submission
from app.schemas import (
    InvitationClaimResponse,
    InvitationCreate,
    InvitationCreatedResponse,
    InvitationTokenRequest,
    InvitationValidationResponse,
)


router = APIRouter(tags=["Invitations"])
INVITATION_DAYS = 7
INVITATION_COLUMNS = (
    "i.id, i.assessment_id, i.invited_email, i.candidate_id, i.expires_at, "
    "i.accepted_at, i.revoked_at, a.status, a.title, a.description, "
    "a.difficulty, a.duration"
)
INVALID_INVITATION_DETAIL = "Invitation link is invalid or unavailable"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _candidate_profile(cursor, user_id: int):
    cursor.execute(
        """SELECT c.id, lower(u.email)
           FROM candidates c JOIN users u ON u.id = c.user_id
           WHERE c.user_id = %s""",
        (user_id,),
    )
    return cursor.fetchone()


def _find_invitation(cursor, token_hash: str, lock: bool = False):
    suffix = " FOR UPDATE OF i" if lock else ""
    cursor.execute(
        f"""SELECT {INVITATION_COLUMNS}
            FROM assessment_invitations i
            JOIN assessments a ON a.id = i.assessment_id
            WHERE i.token_hash = %s{suffix}""",
        (token_hash,),
    )
    return cursor.fetchone()


def _assert_candidate_invitation(invitation, candidate_id: int, account_email: str):
    if invitation is None:
        raise HTTPException(status_code=404, detail=INVALID_INVITATION_DETAIL)
    # Same response for unknown, revoked, expired, and mismatched links avoids
    # disclosing whether a token or invited email exists.
    if invitation[6] is not None or invitation[4] <= datetime.now(timezone.utc):
        raise HTTPException(status_code=404, detail=INVALID_INVITATION_DETAIL)
    if invitation[2].strip().lower() != account_email.strip().lower():
        raise HTTPException(status_code=404, detail=INVALID_INVITATION_DETAIL)
    if invitation[3] is not None and invitation[3] != candidate_id:
        raise HTTPException(status_code=404, detail=INVALID_INVITATION_DETAIL)
    if invitation[3] is None and invitation[7] != "published":
        raise HTTPException(status_code=409, detail="Assessment is no longer accepting invitations")


@router.post(
    "/assessments/{assessment_id}/invitations",
    response_model=InvitationCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_invitation(
    assessment_id: int,
    data: InvitationCreate,
    current_user: dict = Depends(require_role("employer")),
):
    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)
    invited_email = str(data.candidate_email).strip().lower()
    expires_at = datetime.now(timezone.utc) + timedelta(days=INVITATION_DAYS)
    frontend_base_url = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/")
    invitation_url = f"{frontend_base_url}/candidate/invitation/{token}"

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT status FROM assessments WHERE id = %s AND created_by = %s FOR UPDATE",
                (assessment_id, current_user["id"]),
            )
            assessment = cursor.fetchone()
            if assessment is None:
                raise HTTPException(status_code=404, detail="Assessment not found")
            if assessment[0] != "published":
                raise HTTPException(status_code=409, detail="Only published assessments can receive invitations")

            # Locking the assessment serializes reissues for the same owner and
            # ensures unclaimed links are revoked before the replacement is made.
            cursor.execute(
                """UPDATE assessment_invitations
                   SET revoked_at = CURRENT_TIMESTAMP
                   WHERE assessment_id = %s AND invited_email = %s
                     AND candidate_id IS NULL AND revoked_at IS NULL""",
                (assessment_id, invited_email),
            )
            cursor.execute(
                """INSERT INTO assessment_invitations
                       (assessment_id, invited_by, invited_email, token_hash, expires_at)
                   VALUES (%s, %s, %s, %s, %s)
                   RETURNING id, assessment_id, invited_email, expires_at""",
                (assessment_id, current_user["id"], invited_email, token_hash, expires_at),
            )
            created = cursor.fetchone()
        connection.commit()
        return {
            "id": created[0],
            "assessment_id": created[1],
            "candidate_email": created[2],
            "expires_at": created[3],
            "invitation_url": invitation_url,
        }
    except HTTPException:
        connection.rollback()
        raise
    except Exception:
        connection.rollback()
        raise HTTPException(status_code=500, detail="Could not create invitation")
    finally:
        connection.close()


@router.post(
    "/assessments/{assessment_id}/invitations/{invitation_id}/revoke",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_invitation(
    assessment_id: int,
    invitation_id: int,
    current_user: dict = Depends(require_role("employer")),
):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE assessment_invitations i
                   SET revoked_at = CURRENT_TIMESTAMP
                   FROM assessments a
                   WHERE i.id = %s AND i.assessment_id = %s
                     AND a.id = i.assessment_id AND a.created_by = %s
                     AND i.revoked_at IS NULL
                   RETURNING i.id""",
                (invitation_id, assessment_id, current_user["id"]),
            )
            revoked = cursor.fetchone()
            if revoked is None:
                raise HTTPException(status_code=404, detail="Invitation not found")
        connection.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException:
        connection.rollback()
        raise
    except Exception:
        connection.rollback()
        raise HTTPException(status_code=500, detail="Could not revoke invitation")
    finally:
        connection.close()


@router.post("/invitations/validate", response_model=InvitationValidationResponse)
def validate_invitation(
    data: InvitationTokenRequest,
    current_user: dict = Depends(require_role("candidate")),
):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            candidate = _candidate_profile(cursor, current_user["id"])
            if candidate is None:
                raise HTTPException(status_code=404, detail="Candidate profile not found")
            invitation = _find_invitation(cursor, _hash_token(data.token))
            _assert_candidate_invitation(invitation, candidate[0], candidate[1])
        return {
            "invitation_id": invitation[0],
            "assessment_id": invitation[1],
            "assessment_title": invitation[8],
            "description": invitation[9],
            "difficulty": invitation[10],
            "duration": invitation[11],
            "expires_at": invitation[4],
            "claimed": invitation[3] is not None,
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Could not validate invitation")
    finally:
        connection.close()


@router.post("/invitations/claim", response_model=InvitationClaimResponse)
def claim_invitation(
    data: InvitationTokenRequest,
    current_user: dict = Depends(require_role("candidate")),
):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            candidate = _candidate_profile(cursor, current_user["id"])
            if candidate is None:
                raise HTTPException(status_code=404, detail="Candidate profile not found")
            candidate_id, account_email = candidate

            invitation = _find_invitation(cursor, _hash_token(data.token), lock=True)
            _assert_candidate_invitation(invitation, candidate_id, account_email)

            if invitation[3] is None:
                cursor.execute(
                    """UPDATE assessment_invitations
                       SET candidate_id = %s, accepted_at = CURRENT_TIMESTAMP
                       WHERE id = %s AND candidate_id IS NULL AND revoked_at IS NULL
                       RETURNING id""",
                    (candidate_id, invitation[0]),
                )
                if cursor.fetchone() is None:
                    raise HTTPException(status_code=404, detail=INVALID_INVITATION_DETAIL)

            submission, _ = start_submission_for_candidate(
                cursor, candidate_id, invitation[1]
            )
        connection.commit()
        return {
            "invitation_id": invitation[0],
            "assessment_id": invitation[1],
            "submission": _as_submission(submission),
        }
    except HTTPException:
        connection.rollback()
        raise
    except Exception:
        connection.rollback()
        raise HTTPException(status_code=500, detail="Could not claim invitation")
    finally:
        connection.close()
