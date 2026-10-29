#!/usr/bin/env python3
"""Benchmark controller for Lima VMs or dedicated Linux hosts over SSH."""
import argparse
import contextlib
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import select
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid

from backends import LimaBackend, SSHBackend

ROOT = Path(__file__).resolve().parents[1]
TARGET = 'ecobench-target'
RUNNER = 'ecobench-runner'
WORK = '/var/tmp/ecobench'
PROJECT = 'ecobench'
K6 = 'grafana/k6:0.57.0'
BACKEND = LimaBackend()
LEASES = []


def command(args, *, capture=True, check=True, log_file=None, **kwargs):
    if log_file:
        with open(log_file, 'w') as stream:
            result = subprocess.run(args, text=True, stdout=stream,
                                    stderr=subprocess.STDOUT, **kwargs)
        print(Path(log_file).read_text(), end='')
    else:
        result = subprocess.run(args, text=True, stdout=subprocess.PIPE if capture else None,
                                stderr=None, **kwargs)
    if check and result.returncode:
        raise RuntimeError(f'Command failed ({result.returncode}): {args}')
    return result.stdout if capture else result.returncode


def guest(vm, *args, **kwargs):
    check_leases()
    result = command(BACKEND.argv(vm, args), **kwargs)
    check_leases()
    return result


def compose(*args, **kwargs):
    return guest(TARGET, 'sudo', '-n', 'env', f'BENCHMARK_BIND_ADDRESS={BACKEND.bind_address}',
                 'docker', 'compose', '--project-name', PROJECT,
                 '--project-directory', f'{WORK}/benchmark', '-f',
                 f'{WORK}/benchmark/compose.yaml', *args, **kwargs)


def vm_config():
    return '''minimumLimaVersion: 2.0.0
base:
  - template:_images/ubuntu-lts
vmType: vz
arch: aarch64
cpus: 2
memory: 3GiB
disk: 20GiB
mounts: []
containerd:
  system: false
  user: false
networks:
  - lima: user-v2
    interface: ecobench0
portForwards:
  - guestPortRange: [1, 65535]
    ignore: true
provision:
  - mode: system
    script: |
__BOOTSTRAP__
probes:
  - script: |
      #!/bin/sh
      sudo docker info >/dev/null && sudo docker compose version
'''.replace('__BOOTSTRAP__', '\n'.join('      ' + line for line in
                                    (ROOT / 'benchmark/bootstrap.sh').read_text().splitlines()))


def up(storage):
    if sys.platform != 'darwin' or os.uname().machine != 'arm64':
        raise RuntimeError('The VM preset currently requires Apple Silicon macOS.')
    storage = Path(storage).expanduser().resolve()
    # Refuse a missing external mount rather than silently filling the system disk.
    if str(storage).startswith('/Volumes/') and not Path('/Volumes', storage.parts[2]).is_mount():
        raise RuntimeError(f'External volume is not mounted: {storage}')
    storage.mkdir(parents=True, exist_ok=True)
    # Lima requires a short LIMA_HOME because its Unix socket paths are limited.
    if len(str(storage)) > 55:
        raise RuntimeError('Use a shorter VM storage path (at most 55 characters).')
    for vm in (TARGET, RUNNER):
        existing = command(['limactl', 'list', '--json'])
        instances = [json.loads(line) for line in existing.splitlines() if line.strip()]
        if not any(item['name'] == vm for item in instances):
            with tempfile.TemporaryDirectory() as directory:
                config = Path(directory) / f'{vm}.yaml'
                config.write_text(vm_config())
                command(['limactl', 'start', '--yes', '--name', vm, str(config)], capture=False)
        else:
            command(['limactl', 'start', '--yes', vm], capture=False)
    print(f'VMs ready. LIMA_HOME={storage}\n{BACKEND.warning}')


def sync():
    # Copy only the needed source; no writable host mounts inside either VM.
    with tempfile.TemporaryDirectory() as directory:
        archive = Path(directory) / 'source.tar.gz'
        with tarfile.open(archive, 'w:gz') as output:
            for name in source_hashes():
                output.add(ROOT / name, arcname=name, recursive=False)
        for vm in (TARGET, RUNNER):
            guest(vm, 'mkdir', '-p', WORK)
            command(BACKEND.upload_argv(vm, archive, f'{WORK}/source.tar.gz'))
            guest(vm, 'tar', '-xzf', f'{WORK}/source.tar.gz', '-C', WORK)


def prepare():
    preflight()
    manifest = source_hashes()
    sync()
    guest(TARGET, 'sudo', '-n', 'docker', 'build', '-t', 'ecobench/go-pgx-pg:local',
          '-f', f'{WORK}/benchmark/Dockerfile.go', f'{WORK}/service/go-pgx-pg', capture=False)
    compose('pull', 'database', capture=False)
    guest(RUNNER, 'sudo', '-n', 'docker', 'pull', K6, capture=False)
    if source_hashes() != manifest:
        raise RuntimeError('Source changed during prepare; run prepare again')
    for vm in (TARGET, RUNNER):
        guest(vm, 'tee', f'{WORK}/prepared-source.json', input=json.dumps(manifest))


def source_hashes():
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ('benchmark', 'migrations', 'service/go-pgx-pg')
            for p in sorted((ROOT / folder).rglob('*'))
            if p.is_file() and '__pycache__' not in str(p)
            and p.name != 'hosts.local.json'
            and p.resolve() != getattr(BACKEND, 'inventory_path', None)}


def target_ip():
    if BACKEND.name == 'ssh':
        return BACKEND.bind_address
    # user-v2 can replace the default NIC, ignoring its configured interface name.
    # Route lookup selects the reachable private source without sending traffic.
    value = guest(TARGET, 'ip', '-j', '-4', 'route', 'get', '1.1.1.1')
    return json.loads(value)[0]['prefsrc']


def ready(url, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = guest(RUNNER, 'curl', '--silent', '--output', '/dev/null',
                       '--write-out', '%{http_code}', '--head', '--max-time', '2',
                       f'{url}/healthcheck', check=False)
        if result == '204':
            return
        time.sleep(1)
    raise RuntimeError('Application readiness timed out')


def k6(url, scenario, duration, rate, output, *, name, log_file):
    return guest(RUNNER, 'sudo', '-n', 'docker', 'run', '--rm', '--name', name,
                 '--label', 'org.boavizta.ecobench=true',
                 '--network', 'host', '--user', '0:0',
                 '-v', f'{WORK}/benchmark:/scripts:ro', '-v', f'{output}:/results',
                 '-e', f'SERVER_URL={url}', '-e', f'SCENARIO={scenario}',
                 '-e', f'DURATION={duration}s', '-e', f'RATE={rate}', K6,
                 'run', '--summary-export', '/results/k6-summary.json',
                 '/scripts/scenario.js', capture=False, log_file=log_file)


def summarize(samples, k6_summary):
    groups = {}
    for sample in samples:
        groups.setdefault(sample['container'], []).append(sample)
    metrics = k6_summary.get('metrics', {})
    requests = metrics.get('http_reqs', {}).get('count', 0)
    failed = metrics.get('http_req_failed', {}).get('value', 0)
    successful = requests * (1 - failed)
    return {
        'http_requests': requests,
        'successful_http_requests': successful,
        'containers': {name: {
            'cpu_seconds': rows[-1]['cpu_seconds'] - rows[0]['cpu_seconds'],
            'cpu_seconds_per_successful_request': (
                (rows[-1]['cpu_seconds'] - rows[0]['cpu_seconds']) / successful
                if successful else None),
            'peak_sampled_memory_bytes': max(row['memory_bytes'] for row in rows),
            'sample_count': len(rows),
        } for name, rows in groups.items() if len(rows) >= 2},
        'measurement_note': 'CPU deltas bracket the workload, including small start/stop overhead; '
                            'memory is sampled cgroup usage, not process RSS.',
    }


def run(args):
    preflight()
    for vm in (TARGET, RUNNER):
        prepared = json.loads(guest(vm, 'cat', f'{WORK}/prepared-source.json'))
        if prepared != source_hashes():
            raise RuntimeError('Source changed since prepare; run prepare again before measuring')
    results = Path(args.results).resolve()
    results.mkdir(parents=True, exist_ok=True)
    for _ in range(args.repeat):
        run_once(args, results)


@contextlib.contextmanager
def experiment_lock():
    if BACKEND.name == 'ssh':
        # Server-side locks coordinate independent controllers and inventories.
        with remote_locks():
            yield
        return
    # Also protect prepare/stop from changing a running experiment's environment.
    home = Path(os.environ['LIMA_HOME'])
    if not home.is_dir():
        raise RuntimeError('VM storage does not exist; run up first')
    with open(home / 'experiment.lock', 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another operation owns these benchmark VMs') from None
        with remote_locks():
            yield


def check_leases():
    if any(process.poll() is not None for process in LEASES):
        raise RuntimeError('Lost a server lock connection; refusing further remote commands')


@contextlib.contextmanager
def remote_locks():
    # Keep flock alive by holding stdin open; the lock is released on disconnect.
    # Root-owned, host-wide path also prevents different SSH users from racing.
    acquired = []
    try:
        for role in (TARGET, RUNNER):
            errors = tempfile.TemporaryFile(mode='w+t')
            process = subprocess.Popen(BACKEND.argv(role, [
                'sudo', '-n', 'flock', '-n', '-E', '73', '/var/lock/ecobench.lock',
                'sh', '-c', 'printf "ecobench-locked\\n"; exec cat',
            ]), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors, text=True,
                start_new_session=True)
            acquired.append((process, errors))
            readable, _, _ = select.select([process.stdout], [], [], 20)
            if not readable or process.stdout.readline().strip() != 'ecobench-locked':
                errors.seek(0)
                raise RuntimeError(f'{role}: cannot acquire server lock (busy, SSH, or sudo failure): '
                                   + errors.read()[-2000:])
            LEASES.append(process)
        yield
    finally:
        for process, errors in reversed(acquired):
            if process in LEASES:
                LEASES.remove(process)
            process.stdin.close()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            process.stdout.close()
            errors.close()


def preflight():
    machine_ids = []
    for role in (TARGET, RUNNER):
        guest(role, 'bash', '-ec', '''
test "$(uname -s)" = Linux
for tool in python3 curl flock lscpu ip pkill tar; do command -v "$tool" >/dev/null; done
sudo -n docker info >/dev/null
sudo -n docker compose version
''')
        machine_ids.append(guest(role, 'cat', '/etc/machine-id').strip())
    if not all(machine_ids) or machine_ids[0] == machine_ids[1]:
        raise RuntimeError('Target and load generator must be separate hosts with unique machine IDs')
    if BACKEND.name == 'ssh':
        interfaces = json.loads(guest(TARGET, 'ip', '-j', '-4', 'addr'))
        addresses = {item['local'] for interface in interfaces for item in interface.get('addr_info', [])}
        if BACKEND.bind_address not in addresses:
            raise RuntimeError('target.address is not assigned to the target host')


def bootstrap():
    for role in (TARGET, RUNNER):
        guest(role, 'sudo', '-n', 'bash', '-s', input=(ROOT / 'benchmark/bootstrap.sh').read_text(),
              capture=False)
    preflight()


def cleanup():
    # Only our Compose project and explicitly labelled load generators.
    failures = []
    for action in (
        lambda: compose('down', '--volumes', '--remove-orphans', capture=False),
        cleanup_runner,
    ):
        try:
            action()
        except Exception as error:
            failures.append(str(error))
    if failures:
        raise RuntimeError('; '.join(failures))


def cleanup_runner():
    ids = guest(RUNNER, 'sudo', '-n', 'docker', 'ps', '-aq',
                '--filter', 'label=org.boavizta.ecobench=true').split()
    if ids:
        guest(RUNNER, 'sudo', '-n', 'docker', 'rm', '-f', *ids)


def run_once(args, results):
    run_id = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8]
    output = results / run_id
    output.mkdir()
    remote = f'{WORK}/results/{run_id}'
    runner_name = f'ecobench-k6-{run_id.lower()}'
    collector = None
    metadata = {
        'schema_version': 1, 'run_id': run_id, 'status': 'failed',
        'warning': BACKEND.warning, 'energy': {'available': False, 'joules': None},
        'execution': BACKEND.describe(),
        'configuration': vars(args), 'service': 'go-pgx-pg', 'dataset': 'seed-v1',
        'git_commit': command(['git', 'rev-parse', 'HEAD'], cwd=ROOT).strip(),
        'git_dirty': bool(command(['git', 'status', '--porcelain'], cwd=ROOT).strip()),
        'source_sha256': source_hashes(),
    }
    try:
        for vm in (TARGET, RUNNER):
            guest(vm, 'mkdir', '-p', remote)
        for phase in ('validation', 'warmup', 'measurement'):
            guest(RUNNER, 'mkdir', '-p', f'{remote}/{phase}')
        metadata['phase'] = 'startup'
        compose('down', '--volumes', '--remove-orphans', capture=False)
        compose('up', '-d', '--wait', '--wait-timeout', '120', capture=False)
        url = f'http://{target_ip()}:8080'
        ready(url)
        metadata['images'] = json.loads(guest(TARGET, 'sudo', '-n', 'docker', 'image', 'inspect',
                                             'ecobench/go-pgx-pg:local', 'postgres:14.2-bullseye'))
        metadata['runner_image'] = json.loads(guest(RUNNER, 'sudo', '-n', 'docker', 'image', 'inspect', K6))
        metadata['hosts'] = {vm: {'uname': guest(vm, 'uname', '-a').strip(),
                                  'cpu': guest(vm, 'lscpu'),
                                  'memory': guest(vm, 'cat', '/proc/meminfo')}
                             for vm in (TARGET, RUNNER)}
        # Short validation uses the same response checks as the workload.
        metadata['phase'] = 'validation'
        k6(url, args.scenario, 1, 1, f'{remote}/validation', name=runner_name,
           log_file=output / 'validation.log')
        if args.warmup:
            metadata['phase'] = 'warmup'
            k6(url, args.scenario, args.warmup, args.rate, f'{remote}/warmup', name=runner_name,
               log_file=output / 'warmup.log')
        ids = compose('ps', '-q').split()
        metadata['container_ids'] = ids
        metadata['containers'] = json.loads(guest(TARGET, 'sudo', '-n', 'docker', 'inspect', *ids))
        resource_file = open(output / 'resources.jsonl', 'w')
        try:
            with open(output / 'collector.log', 'w') as collector_log:
                collector = subprocess.Popen(
                    BACKEND.argv(TARGET, ['sudo', '-n', 'python3', f'{WORK}/benchmark/collect.py', *ids]),
                    stdout=resource_file, stderr=collector_log)
            deadline = time.monotonic() + 15
            while len((output / 'resources.jsonl').read_text().splitlines()) < len(ids):
                if collector.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('Resource collector failed to start')
                time.sleep(0.1)
            metadata['measurement_started_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            metadata['phase'] = 'measurement'
            k6(url, args.scenario, args.duration, args.rate, f'{remote}/measurement', name=runner_name,
               log_file=output / 'measurement.log')
            metadata['measurement_ended_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        finally:
            try:
                if collector:
                    try:
                        # Match only this run's collector, not unrelated Python processes.
                        guest(TARGET, 'sudo', '-n', 'pkill', '-TERM', '-f',
                              '^python3 ' + re.escape(f'{WORK}/benchmark/collect.py') + ' '
                              + re.escape(' '.join(ids)) + '$', check=False)
                    finally:
                        try:
                            collector.wait(timeout=20)
                        except subprocess.TimeoutExpired:
                            collector.terminate()
                            try:
                                collector.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                collector.kill()
                                collector.wait()
                            raise RuntimeError('Resource collector did not stop cleanly') from None
            finally:
                resource_file.close()
        if collector.returncode:
            raise RuntimeError('Resource collector exited unsuccessfully')
        (output / 'k6-summary.json').write_text(guest(
            RUNNER, 'sudo', '-n', 'cat', f'{remote}/measurement/k6-summary.json'))
        samples = [json.loads(line) for line in (output / 'resources.jsonl').read_text().splitlines()]
        summary = summarize(samples, json.loads((output / 'k6-summary.json').read_text()))
        for container in metadata['containers']:
            if container['Id'] in summary['containers']:
                summary['containers'][container['Id']]['service'] = container['Config']['Labels'][
                    'com.docker.compose.service']
        if len(summary['containers']) != 2:
            raise RuntimeError('Insufficient resource samples')
        (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        metadata['status'] = 'succeeded'
    except BaseException as error:
        metadata['error'] = str(error)
        raise
    finally:
        # Always attempt all artifact collection and cleanup, even after a failed threshold.
        already_failing = sys.exc_info()[0] is not None
        artifacts = [('compose.log', lambda: compose('logs', '--no-color'))]
        for phase, filename in (('measurement', 'k6-summary.json'), ('validation', 'validation.json'),
                                ('warmup', 'warmup.json')):
            if (output / f'{phase}.log').exists() and not (output / filename).exists():
                artifacts.append((filename, lambda phase=phase: guest(
                    RUNNER, 'sudo', '-n', 'cat', f'{remote}/{phase}/k6-summary.json')))
        for filename, action in artifacts:
            try:
                (output / filename).write_text(action() or '')
            except Exception as error:
                metadata.setdefault('artifact_errors', []).append(str(error))
        try:
            cleanup()
        except Exception as error:
            metadata['cleanup_error'] = str(error)
            metadata['status'] = 'failed'
        (output / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
        print(f'Results: {output}\n{BACKEND.warning}')
        if 'cleanup_error' in metadata and not already_failing:
            raise RuntimeError('Benchmark completed but cleanup failed: ' + metadata['cleanup_error'])


def positive(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError('must be positive')
    return number


def main():
    global BACKEND
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--storage', default='/Volumes/Extension/ecobench-vms')
    parser.add_argument('--backend', choices=['lima', 'ssh'], default='lima')
    parser.add_argument('--hosts', help='SSH hosts JSON (required with --backend ssh)')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('up', help='Create/start two VMs on the external volume')
    sub.add_parser('prepare', help='Copy source, build native app, pull images')
    sub.add_parser('status')
    sub.add_parser('stop', help='Stop Lima VMs, or clean remote containers without shutting down servers')
    sub.add_parser('bootstrap', help='Explicit one-time Docker setup on Ubuntu hosts')
    sub.add_parser('doctor', help='Check SSH, sudo, Docker, tools, and separate host identities')
    run_parser = sub.add_parser('run')
    run_parser.add_argument('--scenario', choices=['DATA_LIST', 'DATA_SIMPLE_ANALYTIC'], default='DATA_LIST')
    run_parser.add_argument('--duration', type=positive, default=30, help='Measured seconds')
    run_parser.add_argument('--warmup', type=int, default=10)
    run_parser.add_argument('--rate', type=positive, default=10, help='Requests per second')
    run_parser.add_argument('--repeat', type=positive, default=1)
    run_parser.add_argument('--results', default=str(ROOT / 'results'))
    args = parser.parse_args()
    if args.backend == 'ssh' and not args.hosts:
        parser.error('--backend ssh requires --hosts')
    if args.backend == 'lima' and args.hosts:
        parser.error('--hosts requires --backend ssh')
    if args.backend == 'ssh' and args.command == 'up':
        parser.error('SSH hosts must already exist; use bootstrap for explicit one-time setup')
    if getattr(args, 'warmup', 0) < 0:
        parser.error('--warmup must not be negative')
    os.environ['LIMA_HOME'] = str(Path(args.storage).expanduser().resolve())
    try:
        BACKEND = SSHBackend(args.hosts) if args.backend == 'ssh' else LimaBackend()
        if args.command == 'up':
            up(args.storage)
        elif args.command == 'prepare':
            with experiment_lock():
                prepare()
        elif args.command == 'run':
            with experiment_lock():
                run(args)
        elif args.command == 'status':
            if BACKEND.name == 'lima':
                command(['limactl', 'list'], capture=False)
            else:
                preflight()
                for role in (TARGET, RUNNER):
                    print(role)
                    guest(role, 'sudo', '-n', 'docker', 'ps', capture=False)
        elif args.command == 'doctor':
            preflight()
            print('Both hosts passed preflight checks.')
        elif args.command == 'bootstrap':
            with experiment_lock():
                bootstrap()
        elif args.command == 'stop':
            with experiment_lock():
                if BACKEND.name == 'ssh':
                    cleanup()
                else:
                    for vm in (TARGET, RUNNER):
                        command(['limactl', 'stop', vm], capture=False)
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as error:
        print(f'ecobench: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
