import unittest
from unittest.mock import patch, MagicMock

from app.database import get_connection
from app.main import app
from test_auth_route_access import _AsgiClient


class DatabaseConfigurationTests(unittest.TestCase):
    def test_host_settings_remain_compatible_and_connection_is_bounded(self):
        with patch.dict("os.environ", {"DB_HOST": "db", "DB_PORT": "5432", "DB_NAME": "talentforge",
                                     "DB_USER": "app", "DB_PASSWORD": "test-only"}, clear=True), \
             patch("app.database.psycopg.connect") as connect:
            get_connection()
        connect.assert_called_once_with(host="db", port="5432", dbname="talentforge", user="app",
                                        password="test-only", connect_timeout=10)

    def test_database_url_takes_precedence_and_preserves_explicit_tls_settings(self):
        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://db/test", "DB_HOST": "ignored",
                                     "DB_SSLMODE": "verify-full", "DB_SSLROOTCERT": "/ca.pem",
                                     "DB_CONNECT_TIMEOUT": "5"}, clear=True), \
             patch("app.database.psycopg.connect") as connect:
            get_connection()
        connect.assert_called_once_with("postgresql://db/test", sslmode="verify-full",
                                        sslrootcert="/ca.pem", connect_timeout=5)

    def test_readiness_failure_has_generic_json_response(self):
        with patch("app.main.get_connection", side_effect=RuntimeError("private connection details")):
            response = _AsgiClient(app).request("GET", "/db-test")
        self.assertEqual(response.status, 500)
        self.assertEqual(response.json, {"detail": "Database connection failed"})

    def test_readiness_queries_database_and_closes_connection(self):
        connection = MagicMock()
        with patch("app.main.get_connection", return_value=connection):
            response = _AsgiClient(app).request("GET", "/db-test")
        self.assertEqual(response.status, 200)
        connection.cursor.return_value.__enter__.return_value.execute.assert_called_once_with("SELECT 1")
        connection.close.assert_called_once()
