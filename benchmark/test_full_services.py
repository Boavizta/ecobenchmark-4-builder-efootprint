import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import full_services
import inventory_services
import analyze_full_services


class InventoryTests(unittest.TestCase):
    def test_only_service_dockerfiles_mark_implementations(self):
        tree = [
            {'path': 'service/empty/README.md', 'type': 'blob', 'sha': 'a'},
            {'path': 'service/actual/Dockerfile', 'type': 'blob', 'sha': 'b'},
            {'path': 'service/actual/src/main.rb', 'type': 'blob', 'sha': 'c'},
            {'path': 'runner/Dockerfile', 'type': 'blob', 'sha': 'd'},
        ]
        services = inventory_services.tree_services(tree)
        self.assertFalse(services['empty']['implemented'])
        self.assertTrue(services['actual']['implemented'])
        self.assertNotIn('runner', services)


class FullBenchmarkTests(unittest.TestCase):
    def test_failed_measurement_keeps_raw_cpu_but_not_a_per_request_factor(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = root / 'services/example-pg'
            service.mkdir(parents=True)
            scenario = b'workload'
            (service / 'scenario.js').write_bytes(scenario)
            (root / 'status.json').write_text(json.dumps({
                'warning': 'local only', 'services': {'example-pg': {
                    'status': 'analysis_failed', 'usable': False, 'schema_sha256': 'schema',
                    'scenario_sha256': hashlib.sha256(scenario).hexdigest(), 'error': 'HTTP failures',
                }}}))
            (service / 'k6-summary.json').write_text(json.dumps({'metrics': {
                'http_reqs': {'count': 10}, 'http_req_failed': {'value': 0.1},
                'checks': {'fails': 1},
            }}))
            (service / 'summary.json').write_text(json.dumps({'containers': {
                'test-app': {'cpu_seconds': 2.0, 'cpu_seconds_per_successful_request': 2 / 9,
                             'sample_count': 60, 'peak_sampled_memory_bytes': 1024**2},
            }}))
            result = analyze_full_services.analyze(root)
            row = result['services'][0]
            self.assertEqual(row['app_cpu_seconds'], 2.0)
            self.assertIsNone(row['app_cpu_seconds_per_successful_request'])
            self.assertFalse(row['valid_local_observation'])
            self.assertFalse(row['sufficient_for_footprint_calibration'])
            analyze_full_services.write(root, result)
            self.assertIn('**NO**', (root / 'analysis.md').read_text())

    def test_shared_schema_rejects_extra_framework_tables(self):
        with patch.object(full_services.smoke, 'command', side_effect=['account\nlist\nschema_migrations\ntask', '', '']):
            with self.assertRaisesRegex(RuntimeError, 'changed the shared schema'):
                full_services.schema_snapshot('database', False)

    def test_postgres_and_mysql_use_the_same_business_tables(self):
        for mysql in [False, True]:
            with patch.object(full_services.smoke, 'command', side_effect=['account\nlist\ntask', 'columns', 'indexes']):
                schema = full_services.schema_snapshot('database', mysql)
                self.assertEqual(schema['tables'], ['account', 'list', 'task'])

    def test_failed_run_is_not_presented_as_usable_or_zero_cost(self):
        report = {'services': {'broken': {'status': 'measurement_failed', 'usable': False}}}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            full_services.write_report(output, report)
            self.assertIn('| broken | measurement_failed | — |', (output / 'recap.md').read_text())
            self.assertFalse(json.loads((output / 'status.json').read_text())['services']['broken']['usable'])

    def test_scope_validation_fails_on_phantom_tasks(self):
        with patch.object(full_services, 'request', side_effect=[
            {'id': 'account'}, {'id': 'first'}, {'id': 'second'},
            [{'id': 'first', 'tasks': [{'id': None}]}, {'id': 'second', 'tasks': []}],
        ]):
            with self.assertRaisesRegex(RuntimeError, 'Empty-list scope mismatch'):
                full_services.validate('http://unused')
