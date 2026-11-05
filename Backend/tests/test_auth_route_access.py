"""HTTP-level auth and role tests using only the standard library."""

import asyncio
import json
import unittest
from datetime import datetime
from unittest.mock import patch

from app.main import app
from app.security import create_access_token


class AuthRouteAccessTests(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides.clear()
        self.client = _AsgiClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_candidate_registration_succeeds_and_stores_password_hash(self):
        connection = _FakeConnection(
            existing_user=None,
            registered_user=(501, "Route Test Candidate", "route-test@example.com", "candidate", datetime(2026, 1, 1)),
        )
        with patch("app.main.get_connection", return_value=connection), \
             patch("app.main.hash_password", return_value="encoded-test-hash") as hash_password:
            response = self.client.request(
                "POST", "/register",
                {"full_name": "Route Test Candidate", "email": "route-test@example.com", "password": "safe-test-password", "role": "candidate"},
            )
        self.assertEqual(response.status, 201)
        self.assertEqual(response.json["user"]["role"], "candidate")
        hash_password.assert_called_once_with("safe-test-password")
        insert_params = connection.calls[1][1]
        self.assertEqual(insert_params[2], "encoded-test-hash")
        self.assertNotEqual(insert_params[2], "safe-test-password")

    def test_employer_registration_succeeds(self):
        connection = _FakeConnection(
            existing_user=None,
            registered_user=(511, "Route Test Employer", "route-employer@example.com", "employer", datetime(2026, 1, 1)),
        )
        with patch("app.main.get_connection", return_value=connection), \
             patch("app.main.hash_password", return_value="encoded-employer-hash"):
            response = self.client.request(
                "POST", "/register",
                {"full_name": "Route Test Employer", "email": "route-employer@example.com", "password": "safe-test-password", "role": "employer"},
            )
        self.assertEqual(response.status, 201)
        self.assertEqual(response.json["user"]["role"], "employer")
        self.assertEqual(connection.calls[1][1][3], "employer")

    def test_duplicate_registration_email_returns_409(self):
        connection = _FakeConnection(existing_user=(512,))
        with patch("app.main.get_connection", return_value=connection):
            response = self.client.request(
                "POST", "/register",
                {"full_name": "Duplicate User", "email": "already@example.com", "password": "safe-test-password", "role": "candidate"},
            )
        self.assertEqual(response.status, 409)
        self.assertEqual(response.json["detail"], "Email is already registered")
        self.assertEqual(len(connection.calls), 1)

    def test_registration_rejects_invalid_role(self):
        response = self.client.request(
            "POST", "/register",
            {"full_name": "Invalid Role", "email": "invalid-role@example.com", "password": "safe-test-password", "role": "administrator"},
        )
        self.assertEqual(response.status, 422)

    def test_login_returns_candidate_access_token(self):
        connection = _FakeConnection(
            login_user=(502, "Route Test Candidate", "route-test@example.com", "test-hash", "candidate")
        )
        with patch("app.routers.auth.get_connection", return_value=connection), \
             patch("app.routers.auth.verify_password", return_value=True):
            response = self.client.request(
                "POST", "/auth/login",
                {"email": "route-test@example.com", "password": "safe-test-password"},
            )
        self.assertEqual(response.status, 200)
        self.assertEqual(response.json["token_type"], "bearer")
        self.assertTrue(response.json["access_token"])
        self.assertEqual(response.json["user"]["role"], "candidate")

    def test_login_returns_employer_role_from_backend(self):
        connection = _FakeConnection(
            login_user=(509, "Route Test Employer", "route-employer@example.com", "test-hash", "employer")
        )
        with patch("app.routers.auth.get_connection", return_value=connection), \
             patch("app.routers.auth.verify_password", return_value=True):
            response = self.client.request(
                "POST", "/auth/login",
                {"email": "route-employer@example.com", "password": "safe-test-password"},
            )
        self.assertEqual(response.status, 200)
        self.assertEqual(response.json["user"]["role"], "employer")

    def test_login_rejects_invalid_password(self):
        connection = _FakeConnection(
            login_user=(510, "Route Test Candidate", "route-test@example.com", "test-hash", "candidate")
        )
        with patch("app.routers.auth.get_connection", return_value=connection), \
             patch("app.routers.auth.verify_password", return_value=False):
            response = self.client.request(
                "POST", "/auth/login",
                {"email": "route-test@example.com", "password": "incorrect-test-password"},
            )
        self.assertEqual(response.status, 401)
        self.assertEqual(response.json["detail"], "Invalid email or password")

    def test_missing_token_returns_401(self):
        response = self.client.request("GET", "/candidate-only")
        self.assertEqual(response.status, 401)

    def test_invalid_token_returns_401(self):
        response = self.client.request(
            "GET", "/candidate-only", token="not-a-valid-jwt"
        )
        self.assertEqual(response.status, 401)

    def test_candidate_can_access_candidate_endpoint(self):
        token = create_access_token(503, "candidate")
        response = self.client.request("GET", "/candidate-only", token=token)
        self.assertEqual(response.status, 200)
        self.assertEqual(response.json["user"], {"id": 503, "role": "candidate"})

    def test_employer_cannot_access_candidate_endpoint(self):
        token = create_access_token(504, "employer")
        response = self.client.request("GET", "/candidate-only", token=token)
        self.assertEqual(response.status, 403)

    def test_employer_can_access_employer_endpoint(self):
        token = create_access_token(505, "employer")
        response = self.client.request("GET", "/employer-only", token=token)
        self.assertEqual(response.status, 200)
        self.assertEqual(response.json["user"], {"id": 505, "role": "employer"})

    def test_candidate_cannot_access_employer_endpoint(self):
        token = create_access_token(506, "candidate")
        response = self.client.request("GET", "/employer-only", token=token)
        self.assertEqual(response.status, 403)

    def test_auth_me_requires_a_valid_token_and_returns_token_role(self):
        missing = self.client.request("GET", "/auth/me")
        invalid = self.client.request("GET", "/auth/me", token="not-a-valid-jwt")
        candidate = self.client.request(
            "GET", "/auth/me", token=create_access_token(507, "candidate")
        )
        employer = self.client.request(
            "GET", "/auth/me", token=create_access_token(508, "employer")
        )

        self.assertEqual(missing.status, 401)
        self.assertEqual(invalid.status, 401)
        self.assertEqual(candidate.status, 200)
        self.assertEqual(candidate.json, {"id": 507, "role": "candidate"})
        self.assertEqual(employer.status, 200)
        self.assertEqual(employer.json, {"id": 508, "role": "employer"})

    def test_frontend_origin_can_make_authorized_api_requests(self):
        response = self.client.request(
            "OPTIONS", "/auth/login", origin="http://localhost:5173",
            preflight_method="POST", requested_headers="authorization,content-type",
        )

        self.assertEqual(response.status, 200)
        self.assertEqual(response.headers.get("access-control-allow-origin"), "http://localhost:5173")


class _AsgiClient:
    """Minimal synchronous HTTP client for an ASGI app, with no extra deps."""

    def __init__(self, application):
        self.application = application

    def request(self, method, path, payload=None, token=None, origin=None,
                preflight_method=None, requested_headers=None):
        body = json.dumps(payload).encode() if payload is not None else b""
        headers = [(b"host", b"testserver")]
        if payload is not None:
            headers.append((b"content-type", b"application/json"))
        if token is not None:
            headers.append((b"authorization", f"Bearer {token}".encode()))
        if origin is not None:
            headers.append((b"origin", origin.encode()))
        if preflight_method is not None:
            headers.append((b"access-control-request-method", preflight_method.encode()))
        if requested_headers is not None:
            headers.append((b"access-control-request-headers", requested_headers.encode()))
        messages = []
        delivered = False

        async def receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.disconnect"}

        async def send(message):
            messages.append(message)

        scope = {
            "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1", "method": method, "scheme": "http",
            "path": path, "raw_path": path.encode(), "query_string": b"",
            "root_path": "", "headers": headers, "client": ("testclient", 12345),
            "server": ("testserver", 80),
        }
        asyncio.run(self.application(scope, receive, send))
        start = next(message for message in messages if message["type"] == "http.response.start")
        response_body = b"".join(
            message.get("body", b"") for message in messages
            if message["type"] == "http.response.body"
        )
        return _Response(start["status"], response_body, start.get("headers", []))


class _Response:
    def __init__(self, status, body, headers=None):
        self.status = status
        self.text = body.decode()
        try:
            self.json = json.loads(self.text) if self.text else None
        except json.JSONDecodeError:
            self.json = None
        self.headers = {key.decode().lower(): value.decode() for key, value in (headers or [])}


class _FakeConnection:
    def __init__(self, existing_user=None, registered_user=None, login_user=None):
        self.existing_user = existing_user
        self.registered_user = registered_user
        self.login_user = login_user
        self.calls = []

    def cursor(self):
        return _FakeCursor(self)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


class _FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, query, params):
        self.connection.calls.append((query, params))
        if "SELECT id FROM users" in query:
            self.result = self.connection.existing_user
        elif "INSERT INTO users" in query:
            self.result = self.connection.registered_user
        elif "SELECT id, full_name, email, password_hash, role" in query:
            self.result = self.connection.login_user

    def fetchone(self):
        return self.result


if __name__ == "__main__":
    unittest.main()
