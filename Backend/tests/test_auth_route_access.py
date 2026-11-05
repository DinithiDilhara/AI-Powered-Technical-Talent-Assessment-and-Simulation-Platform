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

    def test_registration_creates_candidate_by_default(self):
        connection = _FakeConnection(
            existing_user=None,
            registered_user=(501, "Route Test Candidate", "route-test@example.com", "candidate", datetime(2026, 1, 1)),
        )
        with patch("app.main.get_connection", return_value=connection), \
             patch("app.main.hash_password", return_value="test-hash"):
            response = self.client.request(
                "POST", "/register",
                {"full_name": "Route Test Candidate", "email": "route-test@example.com", "password": "safe-test-password"},
            )
        self.assertEqual(response.status, 201)
        self.assertEqual(response.json["user"]["role"], "candidate")

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


class _AsgiClient:
    """Minimal synchronous HTTP client for an ASGI app, with no extra deps."""

    def __init__(self, application):
        self.application = application

    def request(self, method, path, payload=None, token=None):
        body = json.dumps(payload).encode() if payload is not None else b""
        headers = [(b"host", b"testserver")]
        if payload is not None:
            headers.append((b"content-type", b"application/json"))
        if token is not None:
            headers.append((b"authorization", f"Bearer {token}".encode()))
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
        return _Response(start["status"], response_body)


class _Response:
    def __init__(self, status, body):
        self.status = status
        self.text = body.decode()
        self.json = json.loads(self.text) if self.text else None


class _FakeConnection:
    def __init__(self, existing_user=None, registered_user=None, login_user=None):
        self.existing_user = existing_user
        self.registered_user = registered_user
        self.login_user = login_user

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
