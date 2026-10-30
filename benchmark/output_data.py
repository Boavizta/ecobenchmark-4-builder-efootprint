"""Normalize measured runs once for presentation and e-footprint output adapters.

No workload is executed here. Missing/simulated energy and mixed-job ambiguity are
preserved rather than filled with inferred physical measurements.
"""
from bisect import bisect_right
from collections import defaultdict
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path

import analyze_full_services


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} must be a finite number')
    return value


def ratio(numerator, denominator):
    return numerator / denominator if numerator is not None and denominator and denominator > 0 else None


def timestamp(value):
    date = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if date.tzinfo is None:
        raise ValueError('Resource timestamps must include their timezone')
    return date.timestamp()


def metric_values(raw):
    return {name: metric.get('values', metric) for name, metric in raw.get('metrics', {}).items()}


def resource_metrics(rows, roles):
    groups = defaultdict(list)
    for row in rows:
        role = roles.get(row['container'])
        if role not in ('application', 'database'):
            continue
        sample = (timestamp(row['timestamp']), finite(row['cpu_seconds'], 'cpu_seconds'),
                  finite(row['memory_bytes'], 'memory_bytes'))
        if sample[1] < 0 or sample[2] < 0:
            raise ValueError('Negative resource counter')
        if groups[role] and (sample[0] <= groups[role][-1][0] or sample[1] < groups[role][-1][1]):
            raise ValueError('Resource timestamp disorder or CPU counter reset')
        groups[role].append(sample)
    if any(len(groups[role]) < 2 for role in ('application', 'database')):
        raise ValueError('Both application and database need at least two resource samples')
    result = {}
    for role, samples in groups.items():
        span = samples[-1][0] - samples[0][0]
        cpu = samples[-1][1] - samples[0][1]
        mean_memory = sum((b[0] - a[0]) * (a[2] + b[2]) / 2 for a, b in zip(samples, samples[1:])) / span
        result.update({f'{role}_cpu_seconds': cpu, f'{role}_mean_cpu_cores': cpu / span,
                       f'{role}_memory_mean_bytes': mean_memory,
                       f'{role}_memory_sampled_peak_bytes': max(sample[2] for sample in samples),
                       f'{role}_sample_count': len(samples), f'{role}_resource_span_seconds': span})
    start = max(samples[0][0] for samples in groups.values())
    end = min(samples[-1][0] for samples in groups.values())
    if end <= start:
        raise ValueError('Application and database resource windows do not overlap')

    def memory_at(samples, t):
        times = [sample[0] for sample in samples]
        i = max(0, min(len(samples) - 2, bisect_right(times, t) - 1))
        a, b = samples[i:i + 2]
        return a[2] + (b[2] - a[2]) * (t - a[0]) / (b[0] - a[0])

    times = sorted({start, end} | {sample[0] for samples in groups.values() for sample in samples if start < sample[0] < end})
    memory = [(t, sum(memory_at(samples, t) for samples in groups.values())) for t in times]
    result['total_memory_aligned_peak_bytes'] = max(value for _, value in memory)
    result['total_memory_mean_bytes'] = sum((b[0] - a[0]) * (a[1] + b[1]) / 2
                                            for a, b in zip(memory, memory[1:])) / (end - start)
    result['total_cpu_seconds'] = result['application_cpu_seconds'] + result['database_cpu_seconds']
    result['total_mean_cpu_cores'] = result['application_mean_cpu_cores'] + result['database_mean_cpu_cores']
    return result


def energy_metadata(metadata):
    energy = metadata.get('energy') or {}
    if metadata.get('simulation') or energy.get('simulation'):
        return {'status': 'simulated', 'joules': None, 'scope': energy.get('scope'),
                'reason': 'Synthetic energy is never a measured presentation/calibration value'}
    # Real synchronized energy ingestion needs an explicit provenance contract.
    # Existing collectors do not yet produce it; do not trust a naked joules number.
    if energy.get('available') or metadata.get('energy_joules') is not None or energy.get('joules') is not None:
        return {'status': 'unverified', 'joules': None, 'scope': energy.get('scope'),
                'reason': 'No supported synchronized physical-energy provenance record'}
    return {'status': 'unavailable', 'joules': None, 'scope': None, 'reason': 'No physical energy collected'}


def normalize(directory, metadata, context, *, full_valid=None):
    raw_files = []
    for name in ('metadata.json', 'k6-summary.json', 'resources.jsonl', 'scenario.js', 'schema.json'):
        path = directory / name
        if path.exists():
            raw_files.append({'path': name, 'sha256': digest(path)})
    raw_path = directory / 'k6-summary.json'
    raw = json.loads(raw_path.read_text()) if raw_path.exists() else {}
    metrics = metric_values(raw)
    issues = []
    counts = metrics.get('http_reqs', {})
    requests = counts.get('count')
    iterations = metrics.get('iterations', {}).get('count')
    failures = metrics.get('http_req_failed', {})
    failure_rate = failures.get('value', failures.get('rate'))
    failed_checks = metrics.get('checks', {}).get('fails')
    for key, value in [('requests', requests), ('iterations', iterations), ('HTTP failure rate', failure_rate), ('failed checks', failed_checks)]:
        if value is None:
            issues.append('Missing ' + key)
        else:
            finite(value, key)
    valid = (metadata.get('status') in ('passed', 'succeeded') and requests is not None and requests > 0
             and iterations is not None and iterations > 0 and failure_rate == 0 and failed_checks == 0)
    if full_valid is not None:
        valid = valid and full_valid
    if any(threshold.get('ok') is False for metric in raw.get('metrics', {}).values()
           for threshold in metric.get('thresholds', {}).values() if isinstance(threshold, dict)):
        valid = False
        issues.append('Failed k6 threshold')
    if metrics.get('dropped_iterations', {}).get('count', 0) > 0:
        valid = False
        issues.append('Dropped workload iterations')
    if not valid:
        issues.append(metadata.get('error', 'Failed or incomplete workload/integrity checks'))
    containers = metadata.get('containers', [])
    roles = {item['Id']: item.get('Config', {}).get('Labels', {}).get('com.docker.compose.service') for item in containers}
    resource_path = directory / 'resources.jsonl'
    for filename, expected in [('scenario.js', metadata.get('scenario_sha256')),
                               ('schema.json', metadata.get('schema_sha256'))]:
        path = directory / filename
        actual = None
        if path.exists():
            actual = (hashlib.sha256(json.dumps(json.loads(path.read_text()), sort_keys=True).encode()).hexdigest()
                      if filename == 'schema.json' else digest(path))
        if expected and actual != expected:
            valid = False
            issues.append('Source integrity mismatch: ' + filename)
    resources = {}
    if resource_path.exists():
        rows = [json.loads(line) for line in resource_path.read_text().splitlines() if line.strip()]
        if full_valid is not None:
            roles = {row['container']: ('application' if row['container'].endswith('-app') else
                                        'database' if row['container'].endswith('-db') else None) for row in rows}
        try:
            resources = resource_metrics(rows, roles)
        except (KeyError, ValueError) as error:
            issues.append(str(error)); valid = False
    else:
        issues.append('Missing resource time series'); valid = False
    is_full = full_valid is not None
    scenario = 'MIXED' if is_full else metadata.get('configuration', {}).get('scenario')
    contract = metadata.get('workload', {})
    atomic = False
    if contract:
        atomic = (not is_full and contract.get('kind') == 'atomic' and contract.get('operations_per_iteration') == 1
                  and contract.get('job_type') == scenario and requests == iterations)
    workload = {'scenario': scenario or 'UNKNOWN', 'kind': 'atomic' if atomic else 'mixed',
                'job_type': scenario if atomic else None,
                'operation_unit': 'HTTP operation' if atomic else 'mixed journey',
                'dataset': metadata.get('dataset', 'full-mixed-validation-v1' if is_full else None),
                'source_sha256': metadata.get('scenario_sha256') or metadata.get('source_sha256', {}).get('benchmark/scenario.js')}
    run_id = metadata.get('run_id', directory.name)
    fingerprint = hashlib.sha256(json.dumps({'files': raw_files, 'service': metadata.get('service', directory.name),
                                             'run_id': run_id}, sort_keys=True).encode()).hexdigest()
    execution = metadata.get('execution') or {'backend': 'docker-local', 'docker': context.get('docker', {})}
    cohort = {'execution': execution, 'workload': workload,
              'duration_seconds': metadata.get('duration_seconds', metadata.get('configuration', {}).get('duration')),
              'vus': metadata.get('vus'), 'rate': metadata.get('configuration', {}).get('rate'),
              'resource_limits': context.get('resource_limits', {'application_cpu': 1, 'application_memory_bytes': 1024**3,
                                                                'database_cpu': 1, 'database_memory_bytes': 1024**3} if is_full else None)}
    cohort_id = hashlib.sha256(json.dumps(cohort, sort_keys=True).encode()).hexdigest()[:16]
    timing = metrics.get('http_req_duration', {})
    values = {**resources, 'http_requests': requests,
              'successful_http_requests': requests * (1 - failure_rate) if requests is not None and failure_rate is not None else None,
              'iterations': iterations, 'iterations_per_second': metrics.get('iterations', {}).get('rate'),
              'requests_per_second': counts.get('rate'), 'http_failure_rate': failure_rate, 'failed_checks': failed_checks,
              'request_duration_mean_seconds': ratio(timing.get('avg'), 1000),
              'request_duration_p95_seconds': ratio(timing.get('p(95)'), 1000),
              'http_upload_bytes': metrics.get('data_sent', {}).get('count'),
              'http_download_bytes': metrics.get('data_received', {}).get('count')}
    for role in ('application', 'database', 'total'):
        values[f'{role}_cpu_seconds_per_operation'] = ratio(values.get(f'{role}_cpu_seconds'), iterations) if valid else None
    for direction in ('upload', 'download'):
        values[f'http_{direction}_bytes_per_operation'] = ratio(values.get(f'http_{direction}_bytes'), iterations) if valid else None
    energy = energy_metadata(metadata)
    return {'schema_version': 'ecobenchmark.observation/v1', 'id': fingerprint,
            'service': metadata.get('service', directory.name), 'run_id': run_id,
            'use_case': metadata.get('use_case', 'default'), 'cohort_id': cohort_id, 'cohort': cohort,
            'workload': workload, 'metrics': values, 'energy': energy,
            'quality': {'valid': bool(valid), 'issues': sorted(set(issues)),
                        'environment': 'local_shared' if execution.get('backend') in ('docker-local', 'lima') else 'remote_unverified',
                        'sufficient_for_calibration': False},
            'provenance': {'run_format': 'full-services' if is_full else 'reference',
                           'input_directory': str(directory),
                           'raw_files': raw_files, 'measurement_commit': context.get('git_commit', metadata.get('git_commit')),
                           'image_id': metadata.get('image_id'), 'source_sha256': metadata.get('source_sha256', {})}}


def load_observations(inputs):
    observations = []
    seen = set()
    for value in inputs:
        root = Path(value).resolve()
        if (root / 'status.json').exists():
            context = json.loads((root / 'status.json').read_text())
            if not isinstance(context.get('services'), dict) or any(isinstance(row, list) for row in context['services'].values()):
                raise ValueError('Expected a full-services manifest, not smoke-attempt histories')
            checks = analyze_full_services.analyze(root)
            valid = {row['service']: row['valid_local_observation'] for row in checks['services']}
            items = [(root / 'services' / name, metadata, context, valid[name])
                     for name, metadata in context['services'].items()]
        else:
            directories = [root] if (root / 'metadata.json').exists() else sorted(root.iterdir())
            items = []
            for directory in directories:
                if not directory.is_dir() or not (directory / 'metadata.json').exists():
                    continue
                metadata = json.loads((directory / 'metadata.json').read_text())
                if metadata.get('schema_version') != 1 or not metadata.get('execution') or not metadata.get('configuration'):
                    raise ValueError(f'Unsupported benchmark input: {directory}; sensor-only/simulated files are not service runs')
                items.append((directory, metadata, metadata, None))
        for directory, metadata, context, full_valid in items:
            record = normalize(directory, metadata, context, full_valid=full_valid)
            if record['id'] not in seen:
                seen.add(record['id']); observations.append(record)
    if not observations:
        raise ValueError('No supported measured benchmark runs found')
    return observations
