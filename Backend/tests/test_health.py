
import unittest

from app.main import app
from test_auth_route_access import _AsgiClient


class HealthRouteTests(unittest.TestCase):
    def test_health_endpoint(self):
        response = _AsgiClient(app).request("GET", "/health")

        self.assertEqual(response.status, 200)
        self.assertEqual(response.json, {"status": "healthy"})
