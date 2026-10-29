#!/usr/bin/env python3
"""Local Docker functional benchmarks, not comparative performance measurements."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
K6 = 'grafana/k6:0.57.0'
PG = 'ecobenchmark-upgrade/postgres:18.6'
MYSQL = 'ecobenchmark-upgrade/mysql:26.10.0'


def command(args, timeout=120, log=None):
    if log:
        with log.open('w') as output:
            subprocess.run(args, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT,
                           timeout=timeout, check=True)
        return ''
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                          timeout=timeout, check=True).stdout.strip()


def available_services():
    return sorted(p.name for p in (ROOT / 'service').iterdir()
                  if p.is_dir() and (p / 'Dockerfile').exists())


def metrics(summary):
    values = {name: metric['values'] for name, metric in summary.get('metrics', {}).items()}
    return {
        'iterations': values.get('iterations', {}).get('count', 0),
        'requests': values.get('http_reqs', {}).get('count', 0),
        'failed_checks': values.get('checks', {}).get('fails', 0),
        'check_rate': values.get('checks', {}).get('rate', 0),
        'http_failure_rate': values.get('http_req_failed', {}).get('rate', 0),
        'http_p95_ms': values.get('http_req_duration', {}).get('p(95)'),
        'scenario_errors': values.get('scenario_errors', {}).get('count', 0),
        'failed_check_names': [check['name'] for check in summary.get('root_group', {}).get('checks', [])
                               if check.get('fails', 0)],
    }


def write_report(output, report):
    (output / 'status.json').write_text(json.dumps(report, indent=2) + '\n')
    lines = ['# Local service smoke benchmarks', '',
             '10 seconds / 1 VU by default. Functional checks only; these are not comparable hardware performance results.', '',
             '| Service | Status | Iterations | Failed checks | Notes |',
             '| --- | --- | ---: | ---: | --- |']
    for name in available_services():
        attempts = report['services'].get(name, [])
        row = attempts[-1] if attempts else {'status': 'pending'}
        note = (', '.join(row.get('failed_check_names', [])) or row.get('error', ''))
        note = note.replace('|', '/').replace('\n', ' ')[:160]
        lines.append(f"| {name} | {row['status']} | {row.get('iterations', '—')} | {row.get('failed_checks', '—')} | {note} |")
    lines.extend(['| ruby-ror-mysql | not implemented | — | — | README only |', ''])
    (output / 'summary.md').write_text('\n'.join(lines))


def wait_database(name, mysql):
    if mysql:
        args = ['docker', 'exec', '-e', 'MYSQL_PWD=mysecretpassword', name, 'mysql',
                '-h', '127.0.0.1', '-uecobench', '-Decobench', '-e', 'SELECT count(*) FROM task']
    else:
        args = ['docker', 'exec', '-e', 'PGPASSWORD=mysecretpassword', name, 'psql',
                '-h', '127.0.0.1', '-U', 'postgres', '-v', 'ON_ERROR_STOP=1', '-c', 'SELECT count(*) FROM task']
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        try:
            command(args, timeout=10)
            return
        except subprocess.CalledProcessError:
            if command(['docker', 'inspect', '-f', '{{.State.Running}}', name]) != 'true':
                raise RuntimeError('database exited during initialization')
            time.sleep(0.5)
    raise RuntimeError('database initialization timed out')


def wait_application(name, port):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if command(['docker', 'inspect', '-f', '{{.State.Running}}', name]) != 'true':
            raise RuntimeError('application exited during startup; see application.log')
        for method in ['HEAD', 'GET']:
            try:
                request = urllib.request.Request(f'http://127.0.0.1:{port}/healthcheck', method=method)
                with urllib.request.urlopen(request, timeout=2) as response:
                    if 200 <= response.status < 300:
                        return
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                pass
        time.sleep(0.25)
    raise RuntimeError('application healthcheck timed out; see application.log')


def run_service(name, output, network, duration, attempt):
    directory = output / name / f'attempt-{attempt}'
    directory.mkdir(parents=True)
    row = {'status': 'building', 'duration_seconds': duration,
           'logs': str(directory.relative_to(ROOT)) if directory.is_relative_to(ROOT) else str(directory)}
    scenario = (ROOT / 'benchmark/service_smoke.js').read_bytes()
    (directory / 'scenario.js').write_bytes(scenario)
    row['scenario_sha256'] = hashlib.sha256(scenario).hexdigest()
    row['started_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    image = f'ecobenchmark-smoke/{name}:local'
    token = uuid.uuid4().hex[:10]
    database, application, runner = [f'ecobench-smoke-{role}-{token}' for role in ['db', 'app', 'k6']]
    created = []
    stage = 'build'
    try:
        print(f'[{name}] building container', flush=True)
        command(['docker', 'build', '--progress=plain', '-t', image, str(ROOT / 'service' / name)],
                timeout=1800, log=directory / 'build.log')
        row['image_id'] = command(['docker', 'image', 'inspect', '-f', '{{.Id}}', image])
        stage = 'startup'
        mysql = name.endswith('-mysql')
        db_env = ['MYSQL_ROOT_PASSWORD=mysecretpassword', 'MYSQL_USER=ecobench',
                  'MYSQL_PASSWORD=mysecretpassword', 'MYSQL_DATABASE=ecobench'] if mysql else ['POSTGRES_PASSWORD=mysecretpassword']
        args = ['docker', 'run', '-d', '--name', database, '--network', network, '--network-alias', 'database']
        for entry in db_env:
            args += ['-e', entry]
        command(args + [MYSQL if mysql else PG])
        created.append(database)
        wait_database(database, mysql)
        compose = json.loads(command(['docker', 'compose', '-f', str(ROOT / 'service' / name / 'docker-compose.yml'),
                                      'config', '--format', 'json']))
        environment = compose['services']['service'].get('environment', {})
        environment['APP_SECRET'] = 'local-smoke-test-only'
        inner_port = 80 if name.startswith('python-') else 8080
        args = ['docker', 'run', '-d', '--name', application, '--network', network,
                '--network-alias', 'service', '--cpus', '1', '--memory', '1g',
                '-p', f'127.0.0.1::{inner_port}']
        for key, value in environment.items():
            args += ['-e', f'{key}={value}']
        command(args + [image])
        created.append(application)
        binding = command(['docker', 'port', application, f'{inner_port}/tcp'])
        wait_application(application, int(binding.rsplit(':', 1)[1]))
        stage = 'benchmark'
        print(f'[{name}] running {duration}s / 1 VU benchmark', flush=True)
        args = ['docker', 'run', '--rm', '--name', runner, '--network', network,
                '--user', f'{os.getuid()}:{os.getgid()}',
                '-v', f'{directory / "scenario.js"}:/scenario.js:ro',
                '-v', f'{directory}:/results', '-e', f'SERVER_HOST=service:{inner_port}',
                '-e', f'DURATION={duration}s', K6, 'run', '/scenario.js']
        created.append(runner)
        command(args, timeout=duration + 60, log=directory / 'benchmark.log')
        row.update(metrics(json.loads((directory / 'summary.json').read_text())))
        if row['iterations'] < 1 or row['check_rate'] != 1 or row['http_failure_rate'] != 0 or row['scenario_errors']:
            raise RuntimeError('benchmark did not pass all functional checks')
        row['status'] = 'passed'
    except (subprocess.SubprocessError, RuntimeError, ValueError, OSError) as exc:
        row['status'] = stage + '_failed'
        row['error'] = str(exc)
        summary = directory / 'summary.json'
        if summary.exists():
            row.update(metrics(json.loads(summary.read_text())))
    finally:
        for container, filename in [(application, 'application.log'), (database, 'database.log')]:
            if container in created:
                logs = subprocess.run(['docker', 'logs', container], capture_output=True, text=True)
                (directory / filename).write_text(logs.stdout + logs.stderr)
        for container in reversed(created):
            subprocess.run(['docker', 'rm', '-f', '-v', container], capture_output=True)
    print(f'[{name}] {row["status"]}', flush=True)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--service', action='append', choices=available_services())
    parser.add_argument('--duration', type=int, default=10)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.duration < 1:
        parser.error('--duration must be positive')
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output = (args.output or ROOT / 'results' / f'service-smoke-{timestamp}').resolve()
    output.mkdir(parents=True, exist_ok=True)
    status = output / 'status.json'
    report = json.loads(status.read_text()) if status.exists() else {'services': {}}
    report['git_commit'] = command(['git', 'rev-parse', 'HEAD'])
    report['git_dirty'] = bool(command(['git', 'status', '--porcelain']))
    report['warning'] = 'Local Docker functional smoke tests; not comparable hardware performance measurements.'
    write_report(output, report)
    network = 'ecobench-smoke-' + uuid.uuid4().hex[:12]
    command(['docker', 'network', 'create', network])
    try:
        command(['docker', 'build', '-t', PG, str(ROOT / 'migrations')], log=output / 'postgres-build.log')
        command(['docker', 'build', '-f', str(ROOT / 'migrations/Dockerfile.mysql'), '-t', MYSQL,
                 str(ROOT / 'migrations')], log=output / 'mysql-build.log')
        command(['docker', 'pull', K6], log=output / 'k6-pull.log')
        for name in args.service or available_services():
            attempts = report['services'].setdefault(name, [])
            attempts.append(run_service(name, output, network, args.duration, len(attempts) + 1))
            write_report(output, report)
    finally:
        subprocess.run(['docker', 'network', 'rm', network], capture_output=True)
    print(f'Report: {output / "summary.md"}', flush=True)
    if any(report['services'][name][-1]['status'] != 'passed' for name in args.service or available_services()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
