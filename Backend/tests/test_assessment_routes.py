import unittest
from datetime import datetime
from unittest.mock import patch

from app.main import app
from app.security import create_access_token
from test_auth_route_access import _AsgiClient


def assessment_row(identifier=21, owner=700, state="draft", technical_role=None):
    return (
        identifier, "API assessment", "Description", technical_role, "medium", 45,
        owner, state, datetime(2026, 1, 1),
    )


class AssessmentRouteTests(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides.clear()
        self.client = _AsgiClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def request(self, method, path, role="employer", user_id=700, payload=None):
        token = create_access_token(user_id, role) if role else None
        return self.client.request(method, path, payload=payload, token=token)

    def with_db(self, connection, callback):
        with patch("app.routers.assessments.get_connection", return_value=connection):
            return callback()

    def test_employer_creates_draft_with_owner_from_token(self):
        connection = _FakeConnection(one=[assessment_row()])
        response = self.with_db(connection, lambda: self.request(
            "POST", "/assessments", payload={
                "title": "API assessment", "description": "Description",
                "difficulty": "medium", "duration": 45,
            }
        ))
        self.assertEqual(response.status, 201)
        self.assertEqual(response.json["status"], "draft")
        self.assertEqual(response.json["created_by"], 700)
        self.assertEqual(connection.cursor_value.calls[0][1][-1], 700)
        self.assertIn("'draft'", connection.cursor_value.calls[0][0])
        self.assertTrue(connection.committed)

    def test_assessment_can_include_a_supported_technical_role(self):
        connection = _FakeConnection(
            one=[assessment_row(technical_role="AI Engineer")]
        )
        response = self.with_db(connection, lambda: self.request(
            "POST", "/assessments", payload={
                "title": "AI assessment", "difficulty": "medium", "duration": 45,
                "technical_role": "AI Engineer",
            }
        ))
        self.assertEqual(response.status, 201)
        self.assertEqual(response.json["technical_role"], "AI Engineer")
        self.assertEqual(connection.cursor_value.calls[0][1][2], "AI Engineer")

    def test_candidate_cannot_create_assessment(self):
        response = self.request("POST", "/assessments", role="candidate", user_id=701,
                                payload={"title":"A", "difficulty":"easy", "duration":10})
        self.assertEqual(response.status, 403)

    def test_create_validation_rejects_invalid_difficulty_and_duration(self):
        for payload in (
            {"title":"A", "difficulty":"extreme", "duration":10},
            {"title":"A", "difficulty":"easy", "duration":0},
            {"title":"", "difficulty":"easy", "duration":10},
            {"title":"A", "difficulty":"easy", "duration":10, "technical_role":"Frontend Engineer"},
        ):
            response = self.request("POST", "/assessments", payload=payload)
            self.assertEqual(response.status, 422)

    def test_employer_list_is_filtered_to_authenticated_owner(self):
        connection = _FakeConnection(many=[[assessment_row(owner=700)]])
        response = self.with_db(connection, lambda: self.request("GET", "/assessments"))
        self.assertEqual(response.status, 200)
        self.assertEqual([row["created_by"] for row in response.json], [700])
        self.assertEqual(connection.cursor_value.calls[0][1], (700,))

    def test_detail_query_scopes_to_owner(self):
        connection = _FakeConnection(one=[assessment_row(owner=700)])
        response = self.with_db(connection, lambda: self.request("GET", "/assessments/21"))
        self.assertEqual(response.status, 200)
        self.assertIn("created_by = %s", connection.cursor_value.calls[0][0])
        self.assertEqual(connection.cursor_value.calls[0][1], (21, 700))

    def test_other_employers_assessment_is_not_found(self):
        connection = _FakeConnection(one=[None])
        response = self.with_db(connection, lambda: self.request("GET", "/assessments/21", user_id=702))
        self.assertEqual(response.status, 404)

    def test_draft_assessment_can_be_updated(self):
        connection = _FakeConnection(one=[("draft",), assessment_row()])
        response = self.with_db(connection, lambda: self.request(
            "PATCH", "/assessments/21", payload={"title":"Revised title"}
        ))
        self.assertEqual(response.status, 200)
        self.assertEqual(connection.cursor_value.calls[1][1], ("Revised title", 21, 700))
        self.assertTrue(connection.committed)

    def test_draft_assessment_technical_role_can_be_updated(self):
        connection = _FakeConnection(
            one=[("draft",), assessment_row(technical_role="SE Intern")]
        )
        response = self.with_db(connection, lambda: self.request(
            "PATCH", "/assessments/21", payload={"technical_role": "SE Intern"}
        ))
        self.assertEqual(response.status, 200)
        self.assertEqual(response.json["technical_role"], "SE Intern")
        self.assertEqual(connection.cursor_value.calls[1][1], ("SE Intern", 21, 700))

    def test_update_rejects_empty_and_null_required_fields(self):
        for payload in ({}, {"title": None}, {"duration": None}):
            response = self.request("PATCH", "/assessments/21", payload=payload)
            self.assertEqual(response.status, 422)

    def test_published_assessment_cannot_be_updated(self):
        connection = _FakeConnection(one=[("published",)])
        response = self.with_db(connection, lambda: self.request(
            "PATCH", "/assessments/21", payload={"title":"Revised"}
        ))
        self.assertEqual(response.status, 409)
        self.assertEqual(len(connection.cursor_value.calls), 1)

    def test_update_of_unowned_assessment_returns_not_found(self):
        connection = _FakeConnection(one=[None])
        response = self.with_db(connection, lambda: self.request(
            "PATCH", "/assessments/21", user_id=702, payload={"title":"Revised"}
        ))
        self.assertEqual(response.status, 404)

    def test_publish_draft(self):
        connection = _FakeConnection(one=[assessment_row(state="published")])
        response = self.with_db(connection, lambda: self.request("POST", "/assessments/21/publish"))
        self.assertEqual(response.status, 200)
        self.assertEqual(response.json["status"], "published")
        self.assertEqual(connection.cursor_value.calls[0][1], ("published", 21, 700, "draft"))

    def test_closed_assessment_cannot_be_republished(self):
        connection = _FakeConnection(one=[None, ("closed",)])
        response = self.with_db(connection, lambda: self.request("POST", "/assessments/21/publish"))
        self.assertEqual(response.status, 409)

    def test_publish_of_unowned_assessment_returns_not_found(self):
        connection = _FakeConnection(one=[None, None])
        response = self.with_db(connection, lambda: self.request(
            "POST", "/assessments/21/publish", user_id=702
        ))
        self.assertEqual(response.status, 404)

    def test_close_published_assessment(self):
        connection = _FakeConnection(one=[assessment_row(state="closed")])
        response = self.with_db(connection, lambda: self.request("POST", "/assessments/21/close"))
        self.assertEqual(response.status, 200)
        self.assertEqual(response.json["status"], "closed")
        self.assertEqual(connection.cursor_value.calls[0][1], ("closed", 21, 700, "published"))

    def test_draft_cannot_be_closed(self):
        connection = _FakeConnection(one=[None, ("draft",)])
        response = self.with_db(connection, lambda: self.request("POST", "/assessments/21/close"))
        self.assertEqual(response.status, 409)

    def test_candidate_can_list_only_published_assessments(self):
        connection = _FakeConnection(many=[[assessment_row(state="published")]])
        response = self.with_db(connection, lambda: self.request(
            "GET", "/assessments/published", role="candidate", user_id=701
        ))
        self.assertEqual(response.status, 200)
        self.assertEqual([item["status"] for item in response.json], ["published"])
        self.assertIn("status = 'published'", connection.cursor_value.calls[0][0])

    def test_employer_cannot_list_published_candidate_feed(self):
        response = self.request("GET", "/assessments/published")
        self.assertEqual(response.status, 403)

    def test_missing_token_cannot_access_assessment_routes(self):
        response = self.client.request("GET", "/assessments/published")
        self.assertEqual(response.status, 401)

    def test_database_error_returns_500_and_rolls_back(self):
        connection = _FakeConnection(error=RuntimeError("database unavailable"))
        response = self.with_db(connection, lambda: self.request(
            "POST", "/assessments", payload={
                "title":"API assessment", "difficulty":"medium", "duration":45,
            }
        ))
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
