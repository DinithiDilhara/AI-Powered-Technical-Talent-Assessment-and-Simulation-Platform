import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.dependencies import check_user_role, get_current_user, require_role
from app.main import register_user
from app.routers.auth import login_user
from app.schemas import UserLogin, UserRegister


class AuthRoleTests(unittest.TestCase):
    def test_registration_defaults_to_candidate(self):
        data = UserRegister(full_name="Candidate One", email="candidate@example.com", password="password123")
        self.assertEqual(data.role.value, "candidate")

    def test_public_registration_rejects_employer_before_database_access(self):
        data = UserRegister(full_name="Employer One", email="employer@example.com", password="password123", role="employer")
        with patch("app.main.get_connection") as connect:
            with self.assertRaises(HTTPException) as raised:
                register_user(data)
        self.assertEqual(raised.exception.status_code, 403)
        connect.assert_not_called()

    def test_login_returns_token_and_role(self):
        cursor = _Cursor((7, "Candidate One", "candidate@example.com", "hashed", "candidate"))
        connection = _Connection(cursor)
        with patch("app.routers.auth.get_connection", return_value=connection), \
             patch("app.routers.auth.verify_password", return_value=True), \
             patch("app.routers.auth.create_access_token", return_value="signed-token"):
            result = login_user(UserLogin(email="candidate@example.com", password="password123"))
        self.assertEqual(result["access_token"], "signed-token")
        self.assertEqual(result["user"]["role"], "candidate")
        self.assertTrue(connection.closed)

    def test_login_rejects_bad_credentials(self):
        connection = _Connection(_Cursor(None))
        with patch("app.routers.auth.get_connection", return_value=connection):
            with self.assertRaises(HTTPException) as raised:
                login_user(UserLogin(email="nobody@example.com", password="password123"))
        self.assertEqual(raised.exception.status_code, 401)
        self.assertTrue(connection.closed)

    def test_role_mismatch_is_forbidden_and_correct_role_allowed(self):
        with self.assertRaises(HTTPException) as raised:
            check_user_role("candidate", "employer")
        self.assertEqual(raised.exception.status_code, 403)
        self.assertTrue(check_user_role("employer", "employer"))

    def test_missing_token_is_unauthorized(self):
        with self.assertRaises(HTTPException) as raised:
            get_current_user(None)
        self.assertEqual(raised.exception.status_code, 401)

    def test_reusable_role_dependency_allows_matching_user(self):
        employer_guard = require_role("employer")
        self.assertEqual(employer_guard({"id": 7, "role": "employer"}), {"id": 7, "role": "employer"})
        with self.assertRaises(HTTPException) as raised:
            employer_guard({"id": 8, "role": "candidate"})
        self.assertEqual(raised.exception.status_code, 403)


class _Cursor:
    def __init__(self, row):
        self.row = row

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, *args):
        pass

    def fetchone(self):
        return self.row


class _Connection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.closed = False

    def cursor(self):
        return self.cursor_value

    def close(self):
        self.closed = True


if __name__ == "__main__":
    unittest.main()
