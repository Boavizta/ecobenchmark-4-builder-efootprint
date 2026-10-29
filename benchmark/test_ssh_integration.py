"""Opt-in real OpenSSH tests against the two already-running Lima VMs.

ECOBENCH_LIMA_SSH_TEST=1 python3 -m unittest discover -s benchmark -p test_ssh_integration.py -v
Never connects to cloud hosts. Uses trusted guest host keys, not ssh-keyscan/TOFU.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import ecobench
from backends import SSHBackend, TARGET, RUNNER


@unittest.skipUnless(os.environ.get('ECOBENCH_LIMA_SSH_TEST') == '1',
                     'Set ECOBENCH_LIMA_SSH_TEST=1 with both Lima VMs running')
class SSHIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.root = Path(cls.directory.name).resolve()
        cls.home = Path(os.environ.get('LIMA_HOME', '/Volumes/Extension/ecobench-vms'))
        cls.env = dict(os.environ, LIMA_HOME=str(cls.home))
        stanzas, keys = [], []
        for role, alias in ((TARGET, 'test-target'), (RUNNER, 'test-runner')):
            generated = (cls.home / role / 'ssh.config').read_text()
            port = re.search(r'^\s*Port (\d+)', generated, re.M).group(1)
            user = re.search(r'^\s*User (\S+)', generated, re.M).group(1)
            host_key = subprocess.check_output(
                ['limactl', 'shell', role, '--', 'cat', '/etc/ssh/ssh_host_ed25519_key.pub'],
                env=cls.env, text=True).strip()
            keys.append(f'[127.0.0.1]:{port} {host_key}')
            stanzas.append(f'''Host {alias}
  HostName 127.0.0.1
  Port {port}
  User {user}
  IdentityFile "{cls.home}/_config/user"
  IdentitiesOnly yes
  UserKnownHostsFile "{cls.root}/known_hosts"
''')
        (cls.root / 'known_hosts').write_text('\n'.join(keys) + '\n')
        (cls.root / 'ssh_config').write_text('\n'.join(stanzas))
        route = subprocess.check_output(
            ['limactl', 'shell', TARGET, '--', 'ip', '-j', '-4', 'route', 'get', '1.1.1.1'],
            env=cls.env, text=True)
        cls.hosts = cls.root / 'hosts.json'
        cls.hosts.write_text(json.dumps({
            'ssh_config': str(cls.root / 'ssh_config'),
            'target': {'host': 'test-target', 'address': json.loads(route)[0]['prefsrc']},
            'runner': {'host': 'test-runner'},
        }))

    def cli(self, *args, success=True):
        result = subprocess.run(
            [sys.executable, str(ecobench.ROOT / 'benchmark/ecobench.py'),
             '--backend', 'ssh', '--hosts', str(self.hosts), *args],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=240, env=self.env)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout[-8000:])
        return result

    def test_bootstrap_prepare_repeated_run_and_cleanup_over_real_ssh(self):
        self.cli('doctor')
        self.cli('bootstrap')
        self.cli('prepare')
        results = self.root / 'results'
        try:
            self.cli('run', '--duration', '2', '--warmup', '1', '--repeat', '2', '--results', str(results))
        finally:
            self.cli('stop')
        runs = sorted(results.iterdir())
        self.assertEqual(len(runs), 2)
        metadata = [json.loads((run / 'metadata.json').read_text()) for run in runs]
        self.assertTrue(all(item['status'] == 'succeeded' for item in metadata))
        self.assertTrue(all(item['execution']['backend'] == 'ssh' for item in metadata))
        self.assertTrue(all(item['energy']['joules'] is None for item in metadata))
        self.assertTrue(set(metadata[0]['container_ids']).isdisjoint(metadata[1]['container_ids']))
        for run in runs:
            summary = json.loads((run / 'summary.json').read_text())
            self.assertEqual({c['service'] for c in summary['containers'].values()},
                             {'application', 'database'})
            self.assertTrue(all(c['sample_count'] >= 2 for c in summary['containers'].values()))
            self.assertGreater((run / 'measurement.log').stat().st_size, 0)
        backend = SSHBackend(self.hosts)
        for role in (TARGET, RUNNER):
            remaining = subprocess.check_output(backend.argv(role, [
                'sudo', '-n', 'docker', 'ps', '-aq', '--filter',
                'label=com.docker.compose.project=ecobench' if role == TARGET else
                'label=org.boavizta.ecobench=true',
            ]), text=True)
            self.assertEqual(remaining.strip(), '')

    def test_remote_lock_rejects_a_second_controller(self):
        with patch.object(ecobench, 'BACKEND', SSHBackend(self.hosts)):
            with ecobench.remote_locks():
                result = self.cli('prepare', success=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('cannot acquire server lock', result.stdout)

    def test_unknown_host_keys_are_rejected(self):
        empty = self.root / 'empty_known_hosts'
        empty.touch()
        backend = SSHBackend(self.hosts)
        args = backend.argv(TARGET, ['true'])
        # Override the test config's trusted key file without changing verification policy.
        args[1:1] = ['-o', f'UserKnownHostsFile={empty}']
        result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Host key verification failed', result.stderr)


if __name__ == '__main__':
    unittest.main()
