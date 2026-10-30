#!/usr/bin/env python3
"""One local mixed-workload measurement per service, with raw resource counters."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import uuid

from ecobench import summarize
import smoke_services as smoke

ROOT = smoke.ROOT
WARNING = ('Local sequential Docker runs on shared Mac/VM hardware; one observation per service. '
           'Not physical energy measurements, a saturation study, or hardware-independent rankings.')


def request(base, path, payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(base + path, data=body, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=15) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError(f'Unexpected HTTP status for {path}: {response.status}')
        return json.load(response)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def validate(base):
    """Identical untimed contract/data preparation; no separate load-test repetition."""
    account = request(base, '/api/accounts', {'login': 'validation-' + uuid.uuid4().hex})
    path = f"/api/accounts/{account['id']}/lists"
    text = 'creationDate accountId listId accountLogin listCount taskAvg'
    lists = [request(base, path, {'name': name}) for name in [text, 'second']]
    rows = request(base, path)
    require(len(rows) == 2 and all(row.get('tasks') == [] for row in rows), 'Empty-list scope mismatch')
    require(all(row.get('creation_date') for row in rows), 'Missing list timestamps')
    expected = {}
    for entry, count in zip(lists, [1, 2]):
        for _ in range(count):
            task = request(base, f"/api/lists/{entry['id']}/tasks", {'name': text, 'description': text})
            require(task.get('name') == text and task.get('description') == text, 'Write content was altered')
            expected[task['id']] = entry['id']
    rows = request(base, path)
    require({row['id'] for row in rows} == {row['id'] for row in lists}, 'List identity mismatch')
    seen = []
    for row in rows:
        for task in row['tasks']:
            require(expected.get(task['id']) == row['id'], 'Task associated with the wrong list')
            require(task['name'] == text and task['description'] == text, 'Persisted content mismatch')
            seen.append(task['id'])
    require(sorted(seen) == sorted(expected), 'Missing or duplicate persisted tasks')
    require(request(base, path, None) != [], 'Missing populated lists')
    require(request(base, path + '?page=1') == [], 'Pagination is not zero based')
    stats = request(base, '/api/stats')
    stat = next((row for row in stats if row.get('account_id') == account['id']), None)
    require(stat is not None and float(stat['list_count']) == 2 and float(stat['task_avg']) == 1.5,
            'Fractional statistics scope mismatch')
    page_account = request(base, '/api/accounts', {'login': 'pages-' + uuid.uuid4().hex})
    page_path = f"/api/accounts/{page_account['id']}/lists"
    expected_lists = [request(base, page_path, {'name': f'page-{i}'})['id'] for i in range(23)]
    pages = [request(base, page_path + f'?page={i}') for i in range(4)]
    require([len(page) for page in pages] == [10, 10, 3, 0], 'Pagination sizes differ from 10/10/3/0')
    actual = [row['id'] for page in pages for row in page]
    require(sorted(actual) == sorted(expected_lists), 'Pagination loses or duplicates lists')
    return {'status': 'passed', 'accounts': 2, 'lists': 25, 'tasks': 3,
            'checks': ['empty lists', 'timestamps', 'task identity/content/ownership',
                       'fractional statistics', 'zero-based 23-list pagination'],
            'note': 'Untimed setup. The same rows are created for every implementation.'}


def source_hashes(name):
    paths = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard',
                                     f'service/{name}', 'migrations', 'runner/scenario.js',
                                     'benchmark/full_services.py', 'benchmark/collect.py'], cwd=ROOT, text=True)
    return {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            for path in sorted(set(paths.splitlines())) if (ROOT / path).is_file()}


def schema_snapshot(database, mysql):
    if mysql:
        args = ['docker', 'exec', '-e', 'MYSQL_PWD=mysecretpassword', database,
                'mysql', '-uecobench', '-Decobench', '--batch', '--skip-column-names', '-e']
        tables = smoke.command(args + ["SELECT table_name FROM information_schema.tables WHERE table_schema='ecobench' ORDER BY table_name"])
        columns = smoke.command(args + ["SELECT table_name,column_name,column_type,is_nullable,column_default FROM information_schema.columns WHERE table_schema='ecobench' ORDER BY table_name,ordinal_position"])
        indexes = smoke.command(args + ["SELECT table_name,index_name,seq_in_index,column_name FROM information_schema.statistics WHERE table_schema='ecobench' ORDER BY table_name,index_name,seq_in_index"])
    else:
        args = ['docker', 'exec', database, 'psql', '-U', 'postgres', '-t', '-A', '-c']
        tables = smoke.command(args + ["SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"])
        columns = smoke.command(args + ["SELECT table_name,column_name,data_type,is_nullable,column_default FROM information_schema.columns WHERE table_schema='public' ORDER BY table_name,ordinal_position"])
        indexes = smoke.command(args + ["SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY tablename,indexname"])
    require(tables.splitlines() == ['account', 'list', 'task'], 'Extra/missing tables: service changed the shared schema')
    return {'tables': tables.splitlines(), 'columns': columns, 'indexes': indexes}


def docker_socket():
    host = os.environ.get('DOCKER_HOST')
    if not host:
        context = json.loads(smoke.command(['docker', 'context', 'inspect']))
        host = context[0]['Endpoints']['docker']['Host']
    if not host.startswith('unix://'):
        raise RuntimeError('Local resource collection requires a Unix-socket Docker context')
    return host[len('unix://'):]


def write_report(output, report):
    (output / 'status.json').write_text(json.dumps(report, indent=2) + '\n')
    lines = ['# One-run-per-service mixed benchmark', '', WARNING, '',
             'Each timed run uses runner/scenario.js, 2 VUs for 60s by default. '
             'App and database each have 1 CPU / 1 GiB. Contract validation is untimed.', '',
             '| Service | Status | Requests | HTTP failures | p95 ms | App CPU s | App sampled peak MiB | Usable? |',
             '| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |']
    for name, row in report['services'].items():
        def value(key):
            item = row.get(key)
            return '—' if item is None else f'{item:.2f}' if isinstance(item, float) else str(item)
        lines.append(f"| {name} | {row['status']} | {value('requests')} | {value('http_failures')} | "
                     f"{value('p95_ms')} | {value('app_cpu_seconds')} | {value('app_peak_mib')} | {row.get('usable', 'pending')} |")
    lines += ['', 'Usable means the contract, completed workload, HTTP checks, resource samples, and process '
              'health passed. It does not establish statistical significance or measured energy.', '']
    (output / 'recap.md').write_text('\n'.join(lines))


def run_service(name, output, duration, vus, socket_path):
    directory = output / 'services' / name
    directory.mkdir(parents=True, exist_ok=False)
    row = {'status': 'build_failed', 'usable': False, 'phase': 'build', 'service': name,
           'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
           'duration_seconds': duration, 'vus': vus, 'logs': str(directory.relative_to(ROOT)),
           'warning': WARNING, 'energy_joules': None, 'source_sha256': source_hashes(name)}
    workload = (ROOT / 'runner/scenario.js').read_bytes()
    (directory / 'scenario.js').write_bytes(workload)
    row['scenario_sha256'] = hashlib.sha256(workload).hexdigest()
    token = 'ecobench-full-' + uuid.uuid4().hex[:12]
    network, database, application, runner = [token + '-' + role for role in ['net', 'db', 'app', 'k6']]
    created = []
    collector = None
    resources = None
    image = f'ecobenchmark-full/{name}:local'
    try:
        print(f'[{name}] build', flush=True)
        smoke.command(['docker', 'build', '--progress=plain', '-t', image, str(ROOT / 'service' / name)],
                      timeout=1800, log=directory / 'build.log')
        row['image_id'] = smoke.command(['docker', 'image', 'inspect', '-f', '{{.Id}}', image])
        row['phase'] = 'startup'
        smoke.command(['docker', 'network', 'create', network])
        mysql = name.endswith('-mysql')
        database_image = smoke.MYSQL if mysql else smoke.PG
        row['database_image_id'] = smoke.command(['docker', 'image', 'inspect', '-f', '{{.Id}}', database_image])
        env = ['MYSQL_ROOT_PASSWORD=mysecretpassword', 'MYSQL_USER=ecobench',
               'MYSQL_PASSWORD=mysecretpassword', 'MYSQL_DATABASE=ecobench'] if mysql else ['POSTGRES_PASSWORD=mysecretpassword']
        args = ['docker', 'run', '-d', '--name', database, '--network', network,
                '--network-alias', 'database', '--cpus', '1', '--memory', '1g']
        for entry in env:
            args += ['-e', entry]
        smoke.command(args + [row['database_image_id']]); created.append(database)
        smoke.wait_database(database, mysql)
        compose = json.loads(smoke.command(['docker', 'compose', '-f', str(ROOT / 'service' / name / 'docker-compose.yml'),
                                            'config', '--format', 'json']))
        environment = compose['services']['service'].get('environment', {})
        environment['APP_SECRET'] = 'local-full-benchmark-only'
        row['environment_keys'] = sorted(environment)
        port = 80 if name.startswith('python-') else 8080
        args = ['docker', 'run', '-d', '--name', application, '--network', network, '--network-alias', 'service',
                '--cpus', '1', '--memory', '1g', '-p', f'127.0.0.1::{port}']
        for key, value in environment.items():
            args += ['-e', f'{key}={value}']
        smoke.command(args + [row['image_id']]); created.append(application)
        outer_port = int(smoke.command(['docker', 'port', application, f'{port}/tcp']).rsplit(':', 1)[1])
        smoke.wait_application(application, outer_port)
        row['phase'] = 'validation'
        schema = schema_snapshot(database, mysql)
        (directory / 'schema.json').write_text(json.dumps(schema, indent=2) + '\n')
        row['schema_sha256'] = hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()
        validation = validate(f'http://127.0.0.1:{outer_port}')
        (directory / 'validation.json').write_text(json.dumps(validation, indent=2) + '\n')
        row['phase'] = 'measurement'
        resources = (directory / 'resources.jsonl').open('w')
        collector = subprocess.Popen([sys.executable, str(ROOT / 'benchmark/collect.py'), application, database],
                                     stdout=resources, stderr=subprocess.PIPE,
                                     env={**os.environ, 'ECOBENCH_DOCKER_SOCKET': socket_path})
        # Ensure the collector has taken its initial snapshots before load starts.
        deadline = time.monotonic() + 15
        while len((directory / 'resources.jsonl').read_text().splitlines()) < 2:
            if collector.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError('Resource collector failed to take initial samples')
            time.sleep(0.1)
        print(f'[{name}] exactly one {duration}s / {vus}-VU measurement', flush=True)
        row['measurement_started_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        created.append(runner)
        smoke.command(['docker', 'run', '--rm', '--name', runner, '--network', network,
                       '--user', f'{os.getuid()}:{os.getgid()}', '-v', f'{directory}:/results',
                       '-e', f'SERVER_HOST=service:{port}', smoke.K6, 'run', '--vus', str(vus),
                       '--duration', f'{duration}s', '--summary-export', '/results/k6-summary.json', '/results/scenario.js'],
                      timeout=duration + 120, log=directory / 'benchmark.log')
        row['measurement_finished_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        collector.terminate(); _, errors = collector.communicate(timeout=20)
        require(collector.returncode == 0, 'Resource collector failed: ' + errors.decode()[-500:])
        collector = None; resources.close(); resources = None
        row['phase'] = 'analysis'
        raw = json.loads((directory / 'k6-summary.json').read_text())
        metrics = raw['metrics']
        samples = [json.loads(line) for line in (directory / 'resources.jsonl').read_text().splitlines()]
        normalized = summarize(samples, raw)
        (directory / 'summary.json').write_text(json.dumps(normalized, indent=2) + '\n')
        row['requests'] = metrics['http_reqs']['count']
        row['iterations'] = metrics.get('iterations', {}).get('count', 0)
        row['http_failures'] = metrics['http_req_failed']['value'] * row['requests']
        row['p95_ms'] = metrics['http_req_duration']['p(95)']
        row['requests_per_second'] = metrics['http_reqs']['rate']
        row['failed_checks'] = metrics['checks']['fails']
        require(row['iterations'] > 0, 'No complete user journey')
        require(row['http_failures'] == 0 and row['failed_checks'] == 0, 'HTTP/check failures under load')
        require('level=error' not in (directory / 'benchmark.log').read_text(), 'k6 script errors occurred')
        require(len(normalized['containers']) == 2, 'Incomplete application/database resource samples')
        app = normalized['containers'][application]
        row['app_cpu_seconds'] = app['cpu_seconds']
        row['app_peak_mib'] = app['peak_sampled_memory_bytes'] / 1024 ** 2
        row['app_cpu_seconds_per_successful_request'] = app['cpu_seconds_per_successful_request']
        row['database_cpu_seconds'] = normalized['containers'][database]['cpu_seconds']
        row['container_states'] = {}
        for role, container in [('application', application), ('database', database)]:
            state = json.loads(smoke.command(['docker', 'inspect', '-f', '{{json .State}}', container]))
            require(state['Running'] and not state['OOMKilled'], f'{role} exited or was OOM killed')
            row['container_states'][role] = state
        require(source_hashes(name) == row['source_sha256'], 'Source changed during the measurement')
        row.update(status='passed', usable=True, phase='complete')
    except (subprocess.SubprocessError, RuntimeError, OSError, ValueError, KeyError) as error:
        row['status'] = row['phase'] + '_failed'
        row['error'] = (f'Command failed; see {row["phase"]} logs' if isinstance(error, subprocess.SubprocessError)
                        else str(error))
    finally:
        if collector is not None:
            collector.terminate()
            try:
                _, errors = collector.communicate(timeout=20)
            except subprocess.TimeoutExpired:
                collector.kill(); _, errors = collector.communicate()
            (directory / 'collector-errors.log').write_bytes(errors)
        if resources is not None:
            resources.close()
        for container, log in [(application, 'application.log'), (database, 'database.log')]:
            if container in created:
                result = subprocess.run(['docker', 'logs', container], capture_output=True, text=True)
                (directory / log).write_text(result.stdout + result.stderr)
        for container in reversed(created):
            subprocess.run(['docker', 'rm', '-f', '-v', container], capture_output=True)
        subprocess.run(['docker', 'network', 'rm', network], capture_output=True)
        (directory / 'metadata.json').write_text(json.dumps(row, indent=2) + '\n')
    print(f"[{name}] {row['status']} usable={row['usable']}", flush=True)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--service', action='append', choices=smoke.available_services())
    parser.add_argument('--duration', type=int, default=60)
    parser.add_argument('--vus', type=int, default=2)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.duration < 1 or args.vus < 1:
        parser.error('Duration and VUs must be positive')
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=True)
    status = output / 'status.json'
    if status.exists():
        parser.error('Output already has a run manifest: no silent repetitions or overwrites')
    info = json.loads(smoke.command(['docker', 'info', '--format', '{{json .}}']))
    report = {'warning': WARNING, 'git_commit': smoke.command(['git', 'rev-parse', 'HEAD']),
              'git_dirty': bool(smoke.command(['git', 'status', '--porcelain'])),
              'duration_seconds': args.duration, 'vus': args.vus,
              'docker': {key: info.get(key) for key in ['ServerVersion', 'OSType', 'Architecture', 'NCPU',
                                                       'MemTotal', 'KernelVersion', 'OperatingSystem', 'ID']},
              'services': {name: {'status': 'pending'} for name in args.service or smoke.available_services()}}
    socket_path = docker_socket()
    write_report(output, report)
    smoke.command(['docker', 'build', '-t', smoke.PG, str(ROOT / 'migrations')], log=output / 'postgres-build.log')
    smoke.command(['docker', 'build', '-f', str(ROOT / 'migrations/Dockerfile.mysql'), '-t', smoke.MYSQL,
                   str(ROOT / 'migrations')], log=output / 'mysql-build.log')
    smoke.command(['docker', 'pull', smoke.K6], log=output / 'k6-pull.log')
    report['k6_image_id'] = smoke.command(['docker', 'image', 'inspect', '-f', '{{.Id}}', smoke.K6])
    for name in report['services']:
        report['services'][name] = run_service(name, output, args.duration, args.vus, socket_path)
        write_report(output, report)
    print('Raw results and recap:', output, flush=True)
    if any(not row.get('usable') for row in report['services'].values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
