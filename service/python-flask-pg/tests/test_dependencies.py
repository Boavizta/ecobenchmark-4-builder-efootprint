import unittest
from decimal import Decimal
from unittest.mock import patch

from app import database, main


class DependencyCompatibilityTest(unittest.TestCase):
    def setUp(self):
        self.client = main.app.test_client()

    def test_postgresql_driver_is_explicit(self):
        self.assertEqual(database._engine.dialect.driver, "psycopg2")

    def test_fractional_statistics_are_serialized(self):
        stats = database.AccountStatistics(
            account_id="id", account_login="test", list_count=2, task_avg=Decimal("1.5")
        )
        with patch.object(database, "get_stats", return_value=[stats]):
            response = self.client.get("/api/stats")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json[0]["task_avg"], 1.5)

    def test_request_validation(self):
        self.assertEqual(self.client.post("/api/accounts", json={}).status_code, 400)

    def test_healthcheck(self):
        with patch.object(database, "is_healthy", return_value=True):
            response = self.client.get("/healthcheck")
        self.assertEqual(response.json, {"ok": True})
