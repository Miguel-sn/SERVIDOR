import os
import unittest
from unittest.mock import patch

os.environ.setdefault("DB_HOST", "test-db")
os.environ.setdefault("DB_PORT", "3306")
os.environ.setdefault("DB_USER", "test-user")
os.environ.setdefault("DB_PASSWORD", "test-password")
os.environ.setdefault("DB_NAME", "test-db")

from app import app


class HealthCheckTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    @patch("app.fetch_one", return_value={"health": 1})
    def test_health_check_validates_database(self, fetch_one_mock):
        resposta = self.client.get("/api/status")

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json, {"status": "ok", "database": "ok"})
        fetch_one_mock.assert_called_once_with("SELECT 1 AS health")

    @patch("app.fetch_one", side_effect=RuntimeError("database unavailable"))
    def test_health_check_reports_database_failure(self, _fetch_one_mock):
        resposta = self.client.get("/api/status")

        self.assertEqual(resposta.status_code, 503)
        self.assertEqual(resposta.json["database"], "unavailable")


if __name__ == "__main__":
    unittest.main()
