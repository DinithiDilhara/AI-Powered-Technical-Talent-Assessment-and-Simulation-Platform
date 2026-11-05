import hashlib
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.main import app
from app.security import create_access_token
from test_auth_route_access import _AsgiClient


def invitation_row(
    invited_email="invitee@example.com", candidate_id=None, assessment_status="published",
    revoked_at=None, expires_at=None,
):
    now = datetime.now(timezone.utc)
    return (
        91, 12, invited_email, candidate_id, expires_at or now + timedelta(days=3),
        now if candidate_id is not None else None, revoked_at, assessment_status,
        "Invited assessment", "Description", "medium", 40,
    )


def submission_row():
    return (
        81, 33, 12, {"task-1": "saved"}, None, "in_progress",
        datetime(2026, 1, 1), None,
    )


class InvitationRouteTests(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides.clear()
        self.client = _AsgiClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def request(self, method, path, payload=None, role="employer", user_id=700):
        token = create_access_token(user_id, role) if role else None
        return self.client.request(method, path, payload=payload, token=token)

    def with_db(self, connection, callback):
        with patch("app.routers.invitations.get_connection", return_value=connection):
            return callback()

    def test_employer_creates_invite_and_database_receives_only_hash(self):
        expires = datetime.now(timezone.utc) + timedelta(days=7)
        connection = _FakeConnection(one=[("published",), (91, 12, "invitee@example.com", expires)])
        response = self.with_db(connection, lambda: self.request(
            "POST", "/assessments/12/invitations", {"candidate_email": "Invitee@Example.com"}
        ))
        self.assertEqual(response.status, 201)
        self.assertEqual(response.json["candidate_email"], "invitee@example.com")
        self.assertTrue(response.json["invitation_url"].startswith("http://localhost:5173/candidate/invitation/"))
        raw_token = response.json["invitation_url"].rsplit("/", 1)[-1]
        stored_hash = connection.cursor_value.calls[2][1][3]
        self.assertEqual(stored_hash, hashlib.sha256(raw_token.encode()).hexdigest())
        self.assertNotIn(raw_token, repr(connection.cursor_value.calls))
        self.assertEqual(connection.cursor_value.calls[1][1], (12, "invitee@example.com"))
        self.assertIn("candidate_id IS NULL", connection.cursor_value.calls[1][0])
        self.assertTrue(connection.committed)

    def test_non_owner_cannot_create_invitation(self):
        connection = _FakeConnection(one=[None])
        response = self.with_db(connection, lambda: self.request(
            "POST", "/assessments/12/invitations", {"candidate_email": "invitee@example.com"}, user_id=701
        ))
        self.assertEqual(response.status, 404)

    def test_only_published_assessments_receive_invitations(self):
        connection = _FakeConnection(one=[("draft",)])
        response = self.with_db(connection, lambda: self.request(
            "POST", "/assessments/12/invitations", {"candidate_email": "invitee@example.com"}
        ))
        self.assertEqual(response.status, 409)
        self.assertTrue(connection.rolled_back)

    def test_reissuing_invitation_revokes_prior_unclaimed_invitation(self):
        connections = [
            _FakeConnection(one=[("published",), (91, 12, "invitee@example.com", datetime.now(timezone.utc))]),
            _FakeConnection(one=[("published",), (92, 12, "invitee@example.com", datetime.now(timezone.utc))]),
        ]
        for connection in connections:
            response = self.with_db(connection, lambda: self.request(
                "POST", "/assessments/12/invitations", {"candidate_email": "invitee@example.com"}
            ))
            self.assertEqual(response.status, 201)
            update_sql, update_params = connection.cursor_value.calls[1]
            self.assertIn("candidate_id IS NULL", update_sql)
            self.assertIn("revoked_at IS NULL", update_sql)
            self.assertEqual(update_params, (12, "invitee@example.com"))
            self.assertTrue(connection.committed)

    def test_employer_can_revoke_own_invitation(self):
        connection = _FakeConnection(one=[(91,)])
        response = self.with_db(connection, lambda: self.request(
            "POST", "/assessments/12/invitations/91/revoke"
        ))
        self.assertEqual(response.status, 204)
        query, params = connection.cursor_value.calls[0]
        self.assertIn("a.created_by = %s", query)
        self.assertEqual(params, (91, 12, 700))

    def test_non_owner_cannot_revoke_invitation(self):
        connection = _FakeConnection(one=[None])
        response = self.with_db(connection, lambda: self.request(
            "POST", "/assessments/12/invitations/91/revoke", user_id=701
        ))
        self.assertEqual(response.status, 404)

    def test_candidates_cannot_create_or_revoke_invitations(self):
        create = self.request(
            "POST", "/assessments/12/invitations", {"candidate_email": "invitee@example.com"}, role="candidate"
        )
        revoke = self.request(
            "POST", "/assessments/12/invitations/91/revoke", role="candidate"
        )
        self.assertEqual(create.status, 403)
        self.assertEqual(revoke.status, 403)

    def test_candidate_validates_matching_invitation(self):
        invitation = invitation_row()
        connection = _FakeConnection(one=[(33, "invitee@example.com"), invitation])
        response = self.with_db(connection, lambda: self.request(
            "POST", "/invitations/validate", {"token": "A" * 43}, role="candidate", user_id=701
        ))
        self.assertEqual(response.status, 200)
        self.assertEqual(response.json["assessment_id"], 12)
        self.assertFalse(response.json["claimed"])
        self.assertNotIn("token", response.json)

    def test_validation_rejects_unknown_token_generically(self):
        connection = _FakeConnection(one=[(33, "invitee@example.com"), None])
        response = self.with_db(connection, lambda: self.request(
            "POST", "/invitations/validate", {"token": "A" * 43}, role="candidate", user_id=701
        ))
        self.assertEqual(response.status, 404)
        self.assertEqual(response.json["detail"], "Invitation link is invalid or unavailable")
        query, params = connection.cursor_value.calls[1]
        self.assertEqual(params, (hashlib.sha256(("A" * 43).encode()).hexdigest(),))
        self.assertNotIn("A" * 43, query)

    def test_validation_rejects_expired_revoked_and_wrong_email(self):
        now = datetime.now(timezone.utc)
        cases = (
            invitation_row(expires_at=now - timedelta(seconds=1)),
            invitation_row(revoked_at=now),
            invitation_row(invited_email="someone-else@example.com"),
            invitation_row(candidate_id=66),
        )
        for row in cases:
            connection = _FakeConnection(one=[(33, "invitee@example.com"), row])
            response = self.with_db(connection, lambda: self.request(
                "POST", "/invitations/validate", {"token": "A" * 43}, role="candidate", user_id=701
            ))
            self.assertEqual(response.status, 404)
            self.assertEqual(response.json["detail"], "Invitation link is invalid or unavailable")

    def test_validation_requires_candidate_profile_and_published_assessment_for_unclaimed_invite(self):
        no_profile = _FakeConnection(one=[None])
        response = self.with_db(no_profile, lambda: self.request(
            "POST", "/invitations/validate", {"token": "A" * 43}, role="candidate", user_id=701
        ))
        self.assertEqual(response.status, 404)

        closed = _FakeConnection(one=[(33, "invitee@example.com"), invitation_row(assessment_status="closed")])
        response = self.with_db(closed, lambda: self.request(
            "POST", "/invitations/validate", {"token": "A" * 43}, role="candidate", user_id=701
        ))
        self.assertEqual(response.status, 409)

    def test_claim_binds_candidate_and_starts_submission(self):
        expires = datetime.now(timezone.utc) + timedelta(days=3)
        row = invitation_row(expires_at=expires)
        connection = _FakeConnection(one=[(33, "invitee@example.com"), row, (91,), None, ("published",), submission_row()])
        response = self.with_db(connection, lambda: self.request(
            "POST", "/invitations/claim", {"token": "B" * 43}, role="candidate", user_id=701
        ))
        self.assertEqual(response.status, 200)
        self.assertEqual(response.json["submission"]["candidate_id"], 33)
        self.assertEqual(response.json["submission"]["assessment_id"], 12)
        claim_sql, claim_params = connection.cursor_value.calls[2]
        self.assertIn("SET candidate_id = %s, accepted_at", claim_sql)
        self.assertEqual(claim_params, (33, 91))
        self.assertTrue(connection.committed)

    def test_same_candidate_can_reuse_claimed_invitation_to_resume_when_closed(self):
        row = invitation_row(candidate_id=33, assessment_status="closed")
        connection = _FakeConnection(one=[(33, "invitee@example.com"), row, submission_row()])
        response = self.with_db(connection, lambda: self.request(
            "POST", "/invitations/claim", {"token": "C" * 43}, role="candidate", user_id=701
        ))
        self.assertEqual(response.status, 200)
        self.assertEqual(response.json["submission"]["id"], 81)
        self.assertEqual(len(connection.cursor_value.calls), 3)

    def test_another_candidate_cannot_claim_invitation(self):
        row = invitation_row(candidate_id=66)
        connection = _FakeConnection(one=[(33, "invitee@example.com"), row])
        response = self.with_db(connection, lambda: self.request(
            "POST", "/invitations/claim", {"token": "C" * 43}, role="candidate", user_id=701
        ))
        self.assertEqual(response.status, 404)
        self.assertEqual(len(connection.cursor_value.calls), 2)

    def test_claim_rejects_expired_or_revoked_invitation(self):
        now = datetime.now(timezone.utc)
        for row in (
            invitation_row(expires_at=now - timedelta(seconds=1)),
            invitation_row(revoked_at=now),
        ):
            connection = _FakeConnection(one=[(33, "invitee@example.com"), row])
            response = self.with_db(connection, lambda: self.request(
                "POST", "/invitations/claim", {"token": "D" * 43}, role="candidate", user_id=701
            ))
            self.assertEqual(response.status, 404)
            self.assertEqual(len(connection.cursor_value.calls), 2)

    def test_candidate_cannot_create_or_change_links_with_employer_token(self):
        no_token = self.client.request("POST", "/invitations/validate", {"token": "E" * 43})
        employer_token = self.request(
            "POST", "/invitations/validate", {"token": "E" * 43}, role="employer"
        )
        self.assertEqual(no_token.status, 401)
        self.assertEqual(employer_token.status, 403)

    def test_invitation_claim_payload_cannot_supply_candidate_identity(self):
        response = self.request(
            "POST", "/invitations/claim", {"token": "F" * 43, "candidate_id": 33}, role="candidate"
        )
        self.assertEqual(response.status, 422)

    def test_database_failures_return_generic_500(self):
        connection = _FakeConnection(error=RuntimeError("database unavailable"))
        response = self.with_db(connection, lambda: self.request(
            "POST", "/assessments/12/invitations", {"candidate_email": "invitee@example.com"}
        ))
        self.assertEqual(response.status, 500)
        self.assertEqual(response.json["detail"], "Could not create invitation")
        self.assertTrue(connection.rolled_back)


class _FakeConnection:
    def __init__(self, one=None, error=None):
        self.cursor_value = _FakeCursor(one or [], error)
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cursor_value

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


class _FakeCursor:
    def __init__(self, one, error):
        self.one = list(one)
        self.error = error
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, query, params):
        self.calls.append((query, params))
        if self.error:
            raise self.error

    def fetchone(self):
        return self.one.pop(0) if self.one else None


if __name__ == "__main__":
    unittest.main()
