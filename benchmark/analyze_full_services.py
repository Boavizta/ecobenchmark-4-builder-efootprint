#!/usr/bin/env python3
"""Derive CSV/JSON/Markdown recaps without rerunning or changing raw measurements."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import zipfile


def analyze(root):
    manifest = json.loads((root / 'status.json').read_text())
    schema_groups = {'postgres': set(), 'mysql': set()}
    workload_hashes = {metadata.get('scenario_sha256') for metadata in manifest['services'].values()}
    for name, metadata in manifest['services'].items():
        family = 'mysql' if name.endswith('-mysql') else 'postgres'
        if metadata.get('schema_sha256'):
            schema_groups[family].add(metadata['schema_sha256'])
    rows = []
    for name, metadata in manifest['services'].items():
        directory = root / 'services' / name
        raw_path = directory / 'k6-summary.json'
        raw = json.loads(raw_path.read_text()) if raw_path.exists() else {}
        metrics = raw.get('metrics', {})
        resource_path = directory / 'summary.json'
        resource = json.loads(resource_path.read_text()) if resource_path.exists() else {}
        containers = resource.get('containers', {})
        app = next((data for key, data in containers.items() if key.endswith('-app')), {})
        db = next((data for key, data in containers.items() if key.endswith('-db')), {})
        family = 'mysql' if name.endswith('-mysql') else 'postgres'
        scenario = directory / 'scenario.js'
        snapshot_matches = (scenario.exists() and hashlib.sha256(scenario.read_bytes()).hexdigest()
                            == metadata.get('scenario_sha256'))
        consistent_schema = len(schema_groups[family]) == 1
        raw_checks_pass = (metrics.get('http_req_failed', {}).get('value') == 0
                           and metrics.get('checks', {}).get('fails') == 0
                           and metrics.get('iterations', {}).get('count', 0) > 0
                           and len(containers) == 2 and app.get('sample_count', 0) >= 2
                           and db.get('sample_count', 0) >= 2)
        valid = bool(metadata.get('usable') and consistent_schema and snapshot_matches
                     and len(workload_hashes) == 1 and raw_checks_pass)
        row = {
            'service': name, 'status': metadata['status'], 'valid_local_observation': valid,
            'sufficient_for_footprint_calibration': False,
            'database': family, 'duration_seconds': metadata.get('duration_seconds'), 'vus': metadata.get('vus'),
            'requests': metrics.get('http_reqs', {}).get('count'),
            'http_failure_rate': metrics.get('http_req_failed', {}).get('value'),
            'failed_checks': metrics.get('checks', {}).get('fails'),
            'requests_per_second': metrics.get('http_reqs', {}).get('rate'),
            'p95_ms': metrics.get('http_req_duration', {}).get('p(95)'),
            'app_cpu_seconds': app.get('cpu_seconds'), 'database_cpu_seconds': db.get('cpu_seconds'),
            'app_sampled_peak_mib': (app['peak_sampled_memory_bytes'] / 1024 ** 2
                                     if 'peak_sampled_memory_bytes' in app else None),
            'app_cpu_seconds_per_successful_request': (app.get('cpu_seconds_per_successful_request') if valid else None),
            'resource_sample_count': app.get('sample_count'),
            'schema_matches_family': consistent_schema, 'workload_snapshot_verified': snapshot_matches,
            'reason': metadata.get('error', '') if not valid else '',
        }
        rows.append(row)
    return {
        'warning': manifest['warning'], 'measurement_parent_commit': manifest.get('git_commit'),
        'measurement_git_dirty': manifest.get('git_dirty'),
        'service_count': len(rows), 'valid_local_observations': sum(row['valid_local_observation'] for row in rows),
        'interpretation': ('Valid observations can support exploratory local resource analysis and reproducibility checks. '
                           'One shared-hardware run with a growing database cannot establish confidence intervals, '
                           'hardware-independent rankings, energy use, or e-footprint calibration factors.'),
        'schema_hashes': {key: sorted(values) for key, values in schema_groups.items()},
        'workload_hashes': sorted(value for value in workload_hashes if value),
        'services': rows,
    }


def write(root, report):
    (root / 'analysis.json').write_text(json.dumps(report, indent=2) + '\n')
    with (root / 'recap.csv').open('w', newline='') as output:
        writer = csv.DictWriter(output, fieldnames=list(report['services'][0]))
        writer.writeheader(); writer.writerows(report['services'])
    lines = ['# Full service benchmark: final analysis', '',
             f"**{report['valid_local_observations']}/{report['service_count']} valid local observations. One timed run per service.**", '',
             report['warning'], '', report['interpretation'], '',
             '| Service | Requests | Failed checks | p95 ms | App CPU s | Sampled peak MiB | Valid locally |',
             '| --- | ---: | ---: | ---: | ---: | ---: | --- |']
    def number(value):
        return '—' if value is None else f'{value:.2f}' if isinstance(value, float) else str(value)
    for row in report['services']:
        lines.append('| ' + row['service'] + ' | ' + ' | '.join(number(row[key]) for key in
                     ['requests', 'failed_checks', 'p95_ms', 'app_cpu_seconds', 'app_sampled_peak_mib'])
                     + ' | ' + ('yes' if row['valid_local_observation'] else '**NO**') + ' |')
    lines += ['', 'Failed-run resource counters remain raw observations, not valid performance factors. '
              'Memory is sampled cgroup usage including cache, not process RSS. CPU deltas include small start/stop overhead.', '',
              '## Invalid observations', '']
    for row in report['services']:
        if not row['valid_local_observation']:
            lines.append(f"- `{row['service']}`: {row['reason']} (HTTP failure rate {row['http_failure_rate']}).")
    lines += ['', 'Raw evidence: `services/<service>/` (k6 summary, resource time series, schema, validation, logs, metadata). '
              'Branch/PR evidence: `inventory/`, `scope-audit.json`, and `scope-audit.md`.', '']
    (root / 'analysis.md').write_text('\n'.join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--bundle', type=Path, help='Optional ZIP outside the input directory')
    args = parser.parse_args()
    root = args.input.resolve()
    report = analyze(root); write(root, report)
    if args.bundle:
        bundle = args.bundle.resolve()
        if bundle.is_relative_to(root):
            parser.error('ZIP must be outside the input directory')
        with zipfile.ZipFile(bundle, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in sorted(root.rglob('*')):
                if path.is_file():
                    archive.write(path, arcname=str(Path(root.name) / path.relative_to(root)))
        print('Raw bundle:', bundle, f'({bundle.stat().st_size / 1024**2:.1f} MiB)')
    print(f"{report['valid_local_observations']}/{report['service_count']} valid; recap: {root / 'analysis.md'}")


if __name__ == '__main__':
    main()
