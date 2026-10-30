import importlib.util
import json
import argparse
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('ecobench', Path(__file__).with_name('ecobench.py'))
ecobench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ecobench)


class BenchmarkTests(unittest.TestCase):
    def test_summary_normalizes_cpu_by_successful_requests(self):
        samples = [
            {'container': 'app', 'cpu_seconds': 2, 'memory_bytes': 100},
            {'container': 'app', 'cpu_seconds': 7, 'memory_bytes': 200},
        ]
        summary = ecobench.summarize(samples, {'metrics': {
            'http_reqs': {'count': 100}, 'http_req_failed': {'value': 0.5},
        }})
        self.assertEqual(summary['successful_http_requests'], 50)
        self.assertEqual(summary['containers']['app']['cpu_seconds'], 5)
        self.assertEqual(summary['containers']['app']['cpu_seconds_per_successful_request'], 0.1)
        self.assertEqual(summary['containers']['app']['peak_sampled_memory_bytes'], 200)

    def test_no_successful_requests_does_not_divide_by_zero(self):
        samples = [{'container': 'app', 'cpu_seconds': n, 'memory_bytes': 1} for n in (0, 1)]
        result = ecobench.summarize(samples, {})
        self.assertIsNone(result['containers']['app']['cpu_seconds_per_successful_request'])

    def test_incomplete_container_is_not_reported_as_measured(self):
        result = ecobench.summarize([{'container': 'app'}], {})
        self.assertEqual(result['containers'], {})

    def test_ready_retries_until_204(self):
        with patch.object(ecobench, 'guest', side_effect=['000', '503', '204']) as guest:
            with patch.object(ecobench.time, 'sleep'):
                ecobench.ready('http://target')
        self.assertEqual(guest.call_count, 3)

    def test_ready_is_bounded(self):
        with patch.object(ecobench.time, 'monotonic', side_effect=[0, 121]):
            with self.assertRaisesRegex(RuntimeError, 'timed out'):
                ecobench.ready('http://target')

    def test_target_address_uses_route_not_ignored_interface_name(self):
        with patch.object(ecobench, 'guest', return_value=json.dumps([
            {'dev': 'eth0', 'prefsrc': '192.168.104.3'},
        ])) as guest:
            self.assertEqual(ecobench.target_ip(), '192.168.104.3')
        self.assertEqual(guest.call_args.args[-4:], ('-4', 'route', 'get', '1.1.1.1'))

    def test_positive_arguments(self):
        self.assertEqual(ecobench.positive('3'), 3)
        for value in ('0', '-1'):
            with self.assertRaises(ecobench.argparse.ArgumentTypeError):
                ecobench.positive(value)

    def test_vm_has_no_host_mounts_and_no_forwarded_ports(self):
        config = ecobench.vm_config()
        self.assertIn('mounts: []', config)
        self.assertIn('ignore: true', config)
        self.assertIn('lima: user-v2', config)

    def test_startup_failure_keeps_metadata_and_attempts_cleanup(self):
        args = argparse.Namespace(scenario='DATA_LIST', duration=3, warmup=0, rate=1)
        with tempfile.TemporaryDirectory() as directory:
            def compose(*arguments, **kwargs):
                if arguments[0] == 'up':
                    raise RuntimeError('database failed readiness')
                return 'application logs' if arguments[0] == 'logs' else ''

            with patch.object(ecobench, 'compose', side_effect=compose) as mocked:
                with patch.object(ecobench, 'guest', return_value=''):
                    with patch.object(ecobench, 'command', return_value='test-commit'):
                        with self.assertRaisesRegex(RuntimeError, 'database failed'):
                            ecobench.run_once(args, Path(directory))
            output = next(Path(directory).iterdir())
            metadata = json.loads((output / 'metadata.json').read_text())
            self.assertEqual(metadata['status'], 'failed')
            self.assertFalse(metadata['energy']['available'])
            self.assertEqual((output / 'compose.log').read_text(), 'application logs')
            self.assertFalse((output / 'summary.json').exists())
            self.assertEqual(sum(call.args[0] == 'down' for call in mocked.call_args_list), 2)

    def test_lock_refuses_concurrent_operations(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {'LIMA_HOME': directory}):
                with patch.object(ecobench, 'remote_locks', ecobench.contextlib.nullcontext):
                    with ecobench.experiment_lock():
                        with self.assertRaisesRegex(RuntimeError, 'Another operation'):
                            with ecobench.experiment_lock():
                                self.fail('second operation acquired lock')

    def test_stale_source_is_rejected_before_database_reset(self):
        with patch.object(ecobench, 'guest', return_value='{}'):
            with patch.object(ecobench, 'compose') as compose:
                with patch.object(ecobench, 'preflight'):
                    with self.assertRaisesRegex(RuntimeError, 'Source changed'):
                        ecobench.run(argparse.Namespace())
        compose.assert_not_called()


if __name__ == '__main__':
    unittest.main()
