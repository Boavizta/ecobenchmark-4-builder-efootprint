"""Command construction for Lima and strict, noninteractive OpenSSH transports."""
import ipaddress
import json
from pathlib import Path
import re
import shlex

TARGET = 'ecobench-target'
RUNNER = 'ecobench-runner'


class LimaBackend:
    name = 'lima'
    bind_address = '0.0.0.0'
    warning = ('Virtualized resource/performance experiment on shared Mac hardware; '
               'not physical energy measurement or hardware-independent reference data.')

    def argv(self, role, args):
        return ['limactl', 'shell', role, '--', *args]

    def upload_argv(self, role, source, destination):
        return ['limactl', 'copy', str(source), f'{role}:{destination}']

    def describe(self):
        return {'backend': self.name}


class SSHBackend:
    name = 'ssh'
    warning = ('Remote Linux resource/performance experiment; energy measurement is unavailable. '
               'Dedicated hardware and sensor availability are not automatically certified.')

    def __init__(self, filename):
        filename = Path(filename).expanduser().resolve()
        self.inventory_path = filename
        config = json.loads(filename.read_text())
        if not isinstance(config, dict) or set(config) - {'target', 'runner', 'ssh_config'}:
            raise ValueError('Hosts file must contain target, runner, and optional ssh_config')
        self.hosts = {}
        self.ssh_config = self._path(config.get('ssh_config'), filename.parent)
        for role, key in ((TARGET, 'target'), (RUNNER, 'runner')):
            host = config.get(key)
            if not isinstance(host, dict) or set(host) - {'host', 'port', 'identity_file', 'address'}:
                raise ValueError(f'{key}: expected host, optional port/identity_file, and target address')
            destination = host.get('host', '')
            if not isinstance(destination, str) or not re.fullmatch(
                    r'(?:[A-Za-z0-9_.-]+@)?[A-Za-z0-9][A-Za-z0-9_.-]*', destination):
                raise ValueError(f'{key}.host must be an SSH alias, hostname, or user@hostname')
            port = host.get('port')
            if port is not None and (type(port) is not int or not 1 <= port <= 65535):
                raise ValueError(f'{key}.port must be an integer from 1 to 65535')
            self.hosts[role] = {
                'host': destination, 'port': port,
                'identity_file': self._path(host.get('identity_file'), filename.parent),
            }
        address = ipaddress.IPv4Address(config['target'].get('address', ''))
        self.bind_address = str(address)
        if address.is_unspecified or address.is_loopback or address.is_multicast:
            raise ValueError('target.address must be an assigned IPv4 address reachable by the runner')
        if self.hosts[TARGET] == self.hosts[RUNNER]:
            raise ValueError('Target and runner must be separate Linux hosts')

    @staticmethod
    def _path(value, parent):
        if value is None:
            return None
        if not isinstance(value, str) or not value:
            raise ValueError('SSH paths must be nonempty strings')
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = parent / path
        if not path.is_file():
            raise ValueError(f'SSH file does not exist: {path}')
        return str(path.resolve())

    def _options(self, role, *, scp=False):
        host = self.hosts[role]
        options = []
        if self.ssh_config:
            options += ['-F', self.ssh_config]
        # Never silently accept changed/unknown host keys or wait for passwords.
        options += ['-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                    '-o', 'ConnectTimeout=10', '-o', 'ServerAliveInterval=5',
                    '-o', 'ServerAliveCountMax=3', '-o', 'ForwardAgent=no',
                    '-o', 'ClearAllForwardings=yes', '-o', 'ControlMaster=no',
                    '-o', 'ControlPath=none']
        if host['port'] is not None:
            options += ['-P' if scp else '-p', str(host['port'])]
        if host['identity_file']:
            options += ['-i', host['identity_file'], '-o', 'IdentitiesOnly=yes']
        return options

    def argv(self, role, args):
        # SSH joins remote arguments through a shell: quote each, unlike local exec.
        return ['ssh', '-T', *self._options(role), '--', self.hosts[role]['host'], shlex.join(args)]

    def upload_argv(self, role, source, destination):
        return ['scp', '-q', *self._options(role, scp=True), '--', str(source),
                f"{self.hosts[role]['host']}:{destination}"]

    def describe(self):
        return {'backend': self.name, 'target': self.hosts[TARGET]['host'],
                'runner': self.hosts[RUNNER]['host'], 'target_address': self.bind_address}
