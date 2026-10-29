import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import smoke_services


class SmokeServiceTests(unittest.TestCase):
    def test_attempt_saves_exact_scenario_even_when_build_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with patch.object(smoke_services, 'command', side_effect=RuntimeError('build failed')):
                row = smoke_services.run_service('example', output, 'unused', 10, 1)
            saved = (output / 'example/attempt-1/scenario.js').read_bytes()
            self.assertEqual(row['status'], 'build_failed')
            self.assertEqual(row['scenario_sha256'], hashlib.sha256(saved).hexdigest())
            self.assertEqual(saved, (smoke_services.ROOT / 'benchmark/service_smoke.js').read_bytes())

    def test_only_implemented_services_are_selected(self):
        names = smoke_services.available_services()
        self.assertEqual(len(names), 19)
        self.assertNotIn('ruby-ror-mysql', names)

    def test_k6_metrics_preserve_failed_checks(self):
        result = smoke_services.metrics({'metrics': {
            'checks': {'values': {'passes': 9, 'fails': 1, 'rate': 0.9}},
            'iterations': {'values': {'count': 2}},
            'http_req_failed': {'values': {'rate': 0}},
        }})
        self.assertEqual(result['failed_checks'], 1)
        self.assertEqual(result['check_rate'], 0.9)
        self.assertEqual(result['iterations'], 2)

    def test_no_iterations_cannot_be_reported_as_success(self):
        result = smoke_services.metrics({'metrics': {}})
        self.assertEqual(result['iterations'], 0)
        self.assertEqual(result['check_rate'], 0)

    def test_report_shows_latest_attempt_without_discarding_failures(self):
        report = {'services': {'example': [
            {'status': 'benchmark_failed', 'iterations': 1, 'failed_checks': 1},
            {'status': 'passed', 'iterations': 10, 'failed_checks': 0},
        ]}}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with patch.object(smoke_services, 'available_services', return_value=['example', 'pending']):
                smoke_services.write_report(output, report)
            markdown = (output / 'summary.md').read_text()
            self.assertIn('| example | passed | 10 | 0 |', markdown)
            self.assertIn('| pending | pending |', markdown)
            saved = json.loads((output / 'status.json').read_text())
            self.assertEqual(len(saved['services']['example']), 2)
