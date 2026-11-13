from unittest.mock import patch

from django.db import OperationalError
from django.test import SimpleTestCase


class HealthEndpointTests(SimpleTestCase):
    def test_liveness_returns_ok_without_database_access(self):
        with patch("config.health.connection") as mocked_connection:
            response = self.client.get("/api/health/live/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        mocked_connection.cursor.assert_not_called()

    def test_readiness_returns_ok_when_database_query_succeeds(self):
        with patch("config.health.connection") as mocked_connection:
            response = self.client.get("/api/health/ready/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "ok",
                "checks": {"database": "ok"},
            },
        )
        mocked_connection.cursor.assert_called_once_with()
        mocked_connection.cursor.return_value.__enter__.return_value.execute.assert_called_once_with(
            "SELECT 1"
        )

    def test_readiness_returns_503_when_database_is_unavailable(self):
        with patch("config.health.connection") as mocked_connection:
            mocked_connection.cursor.side_effect = OperationalError(
                "database connection failed"
            )
            response = self.client.get("/api/health/ready/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {
                "status": "error",
                "checks": {"database": "error"},
            },
        )
        self.assertNotIn("database connection failed", response.content.decode())

    def test_health_endpoints_reject_post(self):
        live_response = self.client.post("/api/health/live/")
        ready_response = self.client.post("/api/health/ready/")

        self.assertEqual(live_response.status_code, 405)
        self.assertEqual(ready_response.status_code, 405)
