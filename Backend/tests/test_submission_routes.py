import json
import unittest
from datetime import datetime
from unittest.mock import patch

from app.main import app
from app.security import create_access_token
from test_auth_route_access import _AsgiClient


def submission_row(state="in_progress", candidate_id=33, submission_id=81):
    return (
        submission_id, candidate_id, 12, {"task-1": "saved answer"}, None,
        state, datetime(2026, 1, 1), datetime(2026, 1, 2) if state != "in_progress" else None,
    )


class SubmissionRouteTests(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides.clear()
        self.client = _AsgiClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def request(self, method, path, payload=None, role="candidate", user_id=700):
        token = create_access_token(user_id, role) if role else None
        return self.client.request(method, path, payload=payload, token=token)

    def with_db(self, connection, callback):
        with patch("app.routers.submissions.get_connection", return_value=connection):
            return callback()

    def test_start_published_assessment_creates_submission_for_profile(self):
        connection = _FakeConnection(one=[(33,), None, ("published",), submission_row()])
        response = self.with_db(connection, lambda: self.request(
            "POST", "/submissions", {"assessment_id": 12}
        ))
        self.assertEqual(response.status, 201)
        self.assertEqual(response.json["candidate_id"], 33)
        self.assertEqual(response.json["status"], "in_progress")
        self.assertEqual(connection.cursor_value.calls[2][1], (12,))
        insert_sql, insert_params = connection.cursor_value.calls[3]
        self.assertIn("ON CONFLICT (candidate_id, assessment_id) DO NOTHING", insert_sql)
        self.assertEqual(insert_params, (33, 12))
        self.assertTrue(connection.committed)

    def test_start_resumes_existing_submission_even_if_assessment_closed(self):
        row = submission_row()
        connection = _FakeConnection(one=[(33,), row])
        response = self.with_db(connection, lambda: self.request(
            "POST", "/submissions", {"assessment_id": 12}
        ))
        self.assertEqual(response.status, 200)
        self.assertEqual(response.json["id"], 81)
        self.assertEqual(len(connection.cursor_value.calls), 2)

    def test_start_rechecks_for_concurrent_resume_before_rejecting_closed_assessment(self):
        connection = _FakeConnection(one=[(33,), None, ("closed",), submission_row()])
        response = self.with_db(connection, lambda: self.request(
            "POST", "/submissions", {"assessment_id": 12}
        ))
        self.assertEqual(response.status, 200)
        self.assertEqual(response.json["status"], "in_progress")

    def test_start_rejects_existing_submitted_attempt(self):
        connection = _FakeConnection(one=[(33,), submission_row("submitted")])
        response = self.with_db(connection, lambda: self.request(
            "POST", "/submissions", {"assessment_id": 12}
        ))
        self.assertEqual(response.status, 409)

    def test_start_requires_existing_candidate_profile(self):
        connection = _FakeConnection(one=[None])
        response = self.with_db(connection, lambda: self.request(
            "POST", "/submissions", {"assessment_id": 12}
        ))
        self.assertEqual(response.status, 404)

    def test_start_returns_404_for_missing_assessment(self):
        connection = _FakeConnection(one=[(33,), None, None])
        response = self.with_db(connection, lambda: self.request(
            "POST", "/submissions", {"assessment_id": 999}
        ))
        self.assertEqual(response.status, 404)

    def test_start_rejects_unpublished_assessment(self):
        connection = _FakeConnection(one=[(33,), None, ("draft",)])
        response = self.with_db(connection, lambda: self.request(
            "POST", "/submissions", {"assessment_id": 12}
        ))
        self.assertEqual(response.status, 409)
        self.assertTrue(connection.rolled_back)

    def test_concurrent_duplicate_start_returns_winning_in_progress_row(self):
        connection = _FakeConnection(one=[(33,), None, ("published",), None, submission_row()])
        response = self.with_db(connection, lambda: self.request(
            "POST", "/submissions", {"assessment_id": 12}
        ))
        self.assertEqual(response.status, 200)
        self.assertEqual(response.json["id"], 81)

    def test_concurrent_duplicate_start_with_terminal_row_returns_409(self):
        connection = _FakeConnection(one=[(33,), None, ("published",), None, submission_row("evaluated")])
        response = self.with_db(connection, lambda: self.request(
            "POST", "/submissions", {"assessment_id": 12}
        ))
        self.assertEqual(response.status, 409)

    def test_start_rejects_invalid_assessment_id(self):
        response = self.request("POST", "/submissions", {"assessment_id": 0})
        self.assertEqual(response.status, 422)

    def test_candidate_lists_only_their_submissions(self):
        connection = _FakeConnection(many=[[submission_row()]])
        response = self.with_db(connection, lambda: self.request("GET", "/submissions/me"))
        self.assertEqual(response.status, 200)
        self.assertEqual([row["id"] for row in response.json], [81])
        self.assertIn("c.user_id = %s", connection.cursor_value.calls[0][0])
        self.assertEqual(connection.cursor_value.calls[0][1], (700,))

    def test_get_own_submission(self):
        connection = _FakeConnection(one=[submission_row()])
        response = self.with_db(connection, lambda: self.request("GET", "/submissions/81"))
        self.assertEqual(response.status, 200)
        self.assertEqual(response.json["candidate_id"], 33)

    def test_get_other_candidates_submission_returns_404(self):
        connection = _FakeConnection(one=[None])
        response = self.with_db(connection, lambda: self.request("GET", "/submissions/81", user_id=701))
        self.assertEqual(response.status, 404)

    def test_save_answers_merges_keys(self):
        updated = (*submission_row()[:3], {"task-1": "saved answer", "task-2": "new answer"}, *submission_row()[4:])
        connection = _FakeConnection(one=[updated])
        response = self.with_db(connection, lambda: self.request(
            "PATCH", "/submissions/81/answers", {"answers": {"task-2": "new answer"}}
        ))
        self.assertEqual(response.status, 200)
        self.assertEqual(response.json["answers"], {"task-1": "saved answer", "task-2": "new answer"})
        query, params = connection.cursor_value.calls[0]
        self.assertIn("|| %s::jsonb", query)
        self.assertEqual(json.loads(params[0]), {"task-2": "new answer"})
        self.assertEqual(params[1:], (81, 700))

    def test_answer_payload_rejects_non_object_and_protected_fields(self):
        for payload in (
            {"answers": ["not", "an", "object"]},
            {"answers": {"task-1": "x"}, "score": 99},
            {"answers": {"task-1": "x"}, "status": "submitted"},
            {"answers": {"task-1": "x"}, "candidate_id": 33},
            {"answers": {"task-1": "x"}, "submitted_at": "2026-01-01T00:00:00"},
            {"answers": {"task-1": "x"}, "started_at": "2026-01-01T00:00:00"},
            {"answers": {"   ": "x"}},
        ):
            response = self.request("PATCH", "/submissions/81/answers", payload)
            self.assertEqual(response.status, 422)

    def test_submitted_submission_cannot_be_edited(self):
        connection = _FakeConnection(one=[None, submission_row("submitted")])
        response = self.with_db(connection, lambda: self.request(
            "PATCH", "/submissions/81/answers", {"answers": {"task-2": "x"}}
        ))
        self.assertEqual(response.status, 409)

    def test_other_candidate_cannot_edit_submission(self):
        connection = _FakeConnection(one=[None])
        response = self.with_db(connection, lambda: self.request(
            "PATCH", "/submissions/81/answers", {"answers": {"task-2": "x"}}, user_id=701
        ))
        self.assertEqual(response.status, 404)

    def test_submitting_in_progress_attempt_sets_terminal_state(self):
        row = submission_row("submitted")
        connection = _FakeConnection(one=[row])
        response = self.with_db(connection, lambda: self.request("POST", "/submissions/81/submit"))
        self.assertEqual(response.status, 200)
        self.assertEqual(response.json["status"], "submitted")
        self.assertIsNotNone(response.json["submitted_at"])
        self.assertIn("status = 'in_progress'", connection.cursor_value.calls[0][0])
        self.assertTrue(connection.committed)

    def test_submitted_attempt_cannot_be_submitted_again(self):
        connection = _FakeConnection(one=[None, submission_row("submitted")])
        response = self.with_db(connection, lambda: self.request("POST", "/submissions/81/submit"))
        self.assertEqual(response.status, 409)

    def test_submit_other_candidates_attempt_returns_404(self):
        connection = _FakeConnection(one=[None, None])
        response = self.with_db(connection, lambda: self.request(
            "POST", "/submissions/81/submit", user_id=701
        ))
        self.assertEqual(response.status, 404)

    def test_employers_are_forbidden_and_missing_tokens_unauthorized(self):
        employer = self.request("GET", "/submissions/me", role="employer")
        missing = self.client.request("GET", "/submissions/me")
        self.assertEqual(employer.status, 403)
        self.assertEqual(missing.status, 401)

    def test_database_failures_return_500_and_rollback_writes(self):
        for method, path, payload in (
            ("POST", "/submissions", {"assessment_id": 12}),
            ("PATCH", "/submissions/81/answers", {"answers": {"task-1": "x"}}),
            ("POST", "/submissions/81/submit", None),
        ):
            connection = _FakeConnection(error=RuntimeError("database unavailable"))
            response = self.with_db(connection, lambda: self.request(method, path, payload))
            self.assertEqual(response.status, 500)
            self.assertTrue(connection.rolled_back)


class _FakeConnection:
    def __init__(self, one=None, many=None, error=None):
        self.cursor_value = _FakeCursor(one or [], many or [], error)
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
    def __init__(self, one, many, error):
        self.one = list(one)
        self.many = list(many)
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

    def fetchall(self):
        return self.many.pop(0) if self.many else []


if __name__ == "__main__":
    unittest.main()
