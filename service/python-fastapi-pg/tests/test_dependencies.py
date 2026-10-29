import unittest
from decimal import Decimal
from unittest.mock import patch

from app import database, main
from pydantic import ValidationError


class DependencyCompatibilityTest(unittest.TestCase):
    def test_postgresql_driver_is_explicit(self):
        self.assertEqual(database._engine.dialect.driver, "psycopg2")

    def test_fractional_statistics_are_preserved(self):
        stats = database.AccountStatistics(
            account_id="id", account_login="test", list_count=2, task_avg=Decimal("1.5")
        )
        self.assertEqual(stats.model_dump()["task_avg"], 1.5)

    def test_request_validation(self):
        with self.assertRaises(ValidationError):
            main.AccountRequest.model_validate({})

    def test_openapi_generation(self):
        self.assertIn("/api/accounts", main.app.openapi()["paths"])

    def test_healthcheck(self):
        with patch.object(database, "is_healthy", return_value=True):
            self.assertEqual(main.healthcheck(), {"ok": True})
