import json
from pathlib import Path
import shlex
import tempfile
import unittest
from unittest.mock import Mock, patch

from backends import LimaBackend, SSHBackend, TARGET, RUNNER
import ecobench


class SSHBackendTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'hosts.json'
        self.config = {
            'target': {'host': 'benchmark@target.example', 'address': '10.0.0.10'},
            'runner': {'host': 'benchmark@runner.example'},
        }

    def backend(self):
        self.path.write_text(json.dumps(self.config))
        return SSHBackend(self.path)

    def test_quotes_every_remote_argument_without_interpreting_shell_syntax(self):
        args = ['printf', '%s', 'value with spaces', "a'b", '$(touch /tmp/unsafe)', 'x; exit 1']
        argv = self.backend().argv(TARGET, args)
        self.assertEqual(argv[0], 'ssh')
        self.assertEqual(argv[-2], 'benchmark@target.example')
        self.assertEqual(shlex.split(argv[-1]), args)

    def test_enforces_host_key_checking_batch_mode_and_connection_limits(self):
        argv = self.backend().argv(TARGET, ['true'])
        for option in ('StrictHostKeyChecking=yes', 'BatchMode=yes', 'ConnectTimeout=10',
                       'ForwardAgent=no', 'ControlPath=none'):
            self.assertIn(option, argv)
        self.assertIn('-T', argv)

    def test_scp_and_ssh_use_same_identity_config_and_port(self):
        root = Path(self.directory.name).resolve()
        (root / 'key with spaces').touch()
        (root / 'ssh_config').touch()
        self.config['target'].update(port=2222, identity_file='key with spaces')
        self.config['ssh_config'] = 'ssh_config'
        backend = self.backend()
        ssh = backend.argv(TARGET, ['true'])
        scp = backend.upload_argv(TARGET, '/local/archive.tar.gz', '/var/tmp/ecobench/source.tar.gz')
        self.assertEqual(ssh[ssh.index('-p') + 1], '2222')
        self.assertEqual(scp[scp.index('-P') + 1], '2222')
        for argv in (ssh, scp):
            self.assertEqual(argv[argv.index('-i') + 1], str(root / 'key with spaces'))
            self.assertEqual(argv[argv.index('-F') + 1], str(root / 'ssh_config'))
        self.assertEqual(scp[-1], 'benchmark@target.example:/var/tmp/ecobench/source.tar.gz')

    def test_rejects_unsafe_or_option_like_destinations(self):
        for destination in ('-oProxyCommand=evil', 'host;echo bad', 'user@host with spaces', ''):
            with self.subTest(destination=destination):
                self.config['target']['host'] = destination
                with self.assertRaises(ValueError):
                    self.backend()

    def test_rejects_invalid_ports_and_missing_target_address(self):
        for port in (0, 65536, True, '22'):
            self.config['target']['port'] = port
            with self.assertRaises(ValueError):
                self.backend()
        del self.config['target']['port']
        del self.config['target']['address']
        with self.assertRaises(ValueError):
            self.backend()

    def test_rejects_unknown_keys_instead_of_silently_ignoring_typos(self):
        self.config['target']['adress'] = '10.0.0.10'
        with self.assertRaises(ValueError):
            self.backend()

    def test_rejects_loopback_wildcard_and_multicast_bind_addresses(self):
        for address in ('0.0.0.0', '127.0.0.1', '127.1.2.3', '224.0.0.1'):
            self.config['target']['address'] = address
            with self.assertRaises(ValueError):
                self.backend()

    def test_ssh_address_does_not_use_lima_route_discovery(self):
        with patch.object(ecobench, 'BACKEND', self.backend()):
            with patch.object(ecobench, 'guest') as guest:
                self.assertEqual(ecobench.target_ip(), '10.0.0.10')
        guest.assert_not_called()

    def test_compose_binds_only_configured_target_address(self):
        with patch.object(ecobench, 'BACKEND', self.backend()):
            with patch.object(ecobench, 'guest', return_value='') as guest:
                ecobench.compose('up', '-d')
        self.assertIn('BENCHMARK_BIND_ADDRESS=10.0.0.10', guest.call_args.args)

    def test_guest_dispatches_to_ssh_backend(self):
        with patch.object(ecobench, 'BACKEND', self.backend()):
            with patch.object(ecobench, 'command', return_value='ok') as command:
                self.assertEqual(ecobench.guest(RUNNER, 'echo', 'hello world'), 'ok')
        self.assertEqual(command.call_args.args[0][0], 'ssh')
        self.assertEqual(command.call_args.args[0][-1], "echo 'hello world'")

    def test_same_physical_host_is_rejected(self):
        with patch.object(ecobench, 'guest', return_value='same-id'):
            with self.assertRaisesRegex(RuntimeError, 'separate hosts'):
                ecobench.preflight()

    def test_ssh_configuration_is_not_uploaded_or_hashed(self):
        backend = self.backend()
        with patch.object(ecobench, 'BACKEND', backend), patch.object(ecobench, 'ROOT', self.path.parent):
            (self.path.parent / 'benchmark').mkdir()
            inventory = self.path.parent / 'benchmark/hosts.local.json'
            inventory.write_text('private inventory')
            (inventory.parent / 'scenario.js').write_text('workload')
            self.assertEqual(set(ecobench.source_hashes()), {'benchmark/scenario.js'})


class LeaseTests(unittest.TestCase):
    def test_lost_lock_prevents_further_commands(self):
        process = Mock()
        process.poll.return_value = 255
        with patch.object(ecobench, 'LEASES', [process]), patch.object(ecobench, 'command') as command:
            with self.assertRaisesRegex(RuntimeError, 'Lost a server lock'):
                ecobench.guest(TARGET, 'true')
        command.assert_not_called()

    def test_lock_connections_are_released_on_exception(self):
        processes = [Mock(), Mock()]
        for process in processes:
            process.stdout.readline.return_value = 'ecobench-locked\n'
            process.poll.return_value = None
        with patch.object(ecobench, 'LEASES', []):
            with patch.object(ecobench.subprocess, 'Popen', side_effect=processes) as popen:
                with patch.object(ecobench.select, 'select', return_value=([True], [], [])):
                    with self.assertRaisesRegex(RuntimeError, 'test failure'):
                        with ecobench.remote_locks():
                            self.assertEqual(len(ecobench.LEASES), 2)
                            raise RuntimeError('test failure')
                self.assertTrue(all(call.kwargs['start_new_session'] for call in popen.call_args_list))
            self.assertEqual(ecobench.LEASES, [])
        for process in processes:
            process.stdin.close.assert_called_once()
            process.wait.assert_called_once()

    def test_lima_arguments_remain_local_exec_arguments(self):
        self.assertEqual(LimaBackend().argv(TARGET, ['echo', 'a b']),
                         ['limactl', 'shell', TARGET, '--', 'echo', 'a b'])

    def test_cleanup_attempts_runner_even_when_target_is_unreachable(self):
        with patch.object(ecobench, 'compose', side_effect=RuntimeError('target unreachable')):
            with patch.object(ecobench, 'cleanup_runner') as runner:
                with self.assertRaisesRegex(RuntimeError, 'target unreachable'):
                    ecobench.cleanup()
        runner.assert_called_once()


if __name__ == '__main__':
    unittest.main()
