#!/usr/bin/env python3
"""Generate presentation and e-footprint research outputs without running workloads."""
import argparse
from collections import defaultdict
import csv
import html
import json
from pathlib import Path
import statistics
import zipfile

from output_data import load_observations, digest
from footprint_output import export_profiles, legacy_rows, LEGACY_COLUMNS


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def write_csv(path, rows, columns):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader(); writer.writerows(rows)


def repeat_statistics(rows):
    groups = defaultdict(list)
    for row in rows:
        if row['quality']['valid']:
            groups[(row['cohort_id'], row['service'], row['use_case'])].append(row)
    output = []
    for (cohort, service, use_case), runs in sorted(groups.items()):
        for metric in runs[0]['metrics']:
            values = [run['metrics'].get(metric) for run in runs]
            values = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
            if not values:
                continue
            output.append({'cohort_id': cohort, 'service': service, 'use_case': use_case,
                           'metric': metric, 'n': len(values), 'mean': statistics.mean(values),
                           'median': statistics.median(values),
                           'stdev': statistics.stdev(values) if len(values) > 1 else None,
                           'min': min(values), 'max': max(values)})
    return output


def notebook():
    cells = []
    def cell(kind, text):
        item = {'id': f'cell-{len(cells)}', 'cell_type': kind, 'metadata': {}, 'source': text.splitlines(keepends=True)}
        if kind == 'code':
            item.update(execution_count=None, outputs=[])
        cells.append(item)
    cell('markdown', '# Eco-benchmark evidence\n\nRun from this directory. Requires pandas and matplotlib. '
         'Failed runs are excluded from comparisons, not deleted. Cohorts must not be pooled. '
         'One observation is not a boxplot or uncertainty estimate. Energy remains unavailable; '
         'CPU seconds are not joules. An operation in the mixed campaign is an entire journey, not one HTTP request.\n')
    cell('code', "import json\nfrom pathlib import Path\nimport pandas as pd\nimport matplotlib.pyplot as plt\n"
         "df = pd.read_csv('presentation.csv')\ndf['testcase'] = df.service + '/' + df.use_case\ndf[['service', 'valid', 'energy_status', 'operation_unit']]\n")
    cell('code', "valid = df[df.valid == True]\nfor cohort, group in valid.groupby('cohort_id'):\n"
         "    for metric in ['requests_per_second', 'total_cpu_seconds_per_operation', 'total_memory_mean_bytes']:\n"
         "        ax = group.boxplot(column=metric, by='testcase', rot=90) if group.groupby('testcase').size().min() > 1 else group.plot.bar(x='testcase', y=metric, legend=False)\n"
         "        ax.set_title(f'{cohort}: {metric} (individual runs; see repeat counts)')\n"
         "        plt.tight_layout()\n        plt.show()\n")
    cell('code', "pd.read_csv('repeat-statistics.csv')[['service', 'metric', 'n', 'mean', 'stdev']]\n")
    cell('markdown', '## e-footprint readiness\nNo independent DATA_* coefficients or hardware-independent boost factors '
         'are identifiable from a mixed run. See readiness.md and efootprint.json. '
         'A calibrated Job requires cores held for a duration, decimal MB_ram, bytes transferred and durable bytes stored.\n')
    return {'nbformat': 4, 'nbformat_minor': 5, 'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'}}, 'cells': cells}


def generate(inputs, output, *, legacy=False):
    rows = load_observations(inputs)
    # Refuse overwriting any earlier generated or user evidence directory.
    output = Path(output)
    archive = output.with_suffix('.zip')
    if archive.exists():
        raise FileExistsError(archive)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'observations.json', rows)
    write_json(output / 'export-provenance.json', {
        'schema_version': 'ecobenchmark.export/v1',
        'generator_sha256': {name: digest(Path(__file__).parent / name)
                             for name in ('output_data.py', 'export_outputs.py', 'footprint_output.py')},
        'observation_ids': [row['id'] for row in rows], 'benchmarks_executed': False})
    flat = [{'observation_id': r['id'], 'service': r['service'], 'use_case': r['use_case'],
             'cohort_id': r['cohort_id'], 'valid': r['quality']['valid'],
             'issues': '; '.join(r['quality']['issues']), 'operation_unit': r['workload']['operation_unit'],
             'energy_status': r['energy']['status'], 'joules': r['energy']['joules'], **r['metrics']} for r in rows]
    columns = list(dict.fromkeys(key for row in flat for key in row))
    write_csv(output / 'presentation.csv', flat, columns)
    stats = repeat_statistics(rows)
    write_csv(output / 'repeat-statistics.csv', stats, ['cohort_id', 'service', 'use_case', 'metric', 'n', 'mean', 'median', 'stdev', 'min', 'max'])
    write_json(output / 'ecobenchmark.ipynb', notebook())
    profiles = export_profiles(rows)
    write_json(output / 'efootprint.json', profiles)
    text = '# e-footprint readiness\n\nCurrent consumer: `' + profiles['consumer_commit'] + '`\n\n'
    for p in profiles['profiles']:
        text += '## ' + p['service'] + ' — ' + p['status'] + '\n\n' + ''.join('- ' + b + '\n' for b in p['blockers']) + '\n'
    (output / 'readiness.md').write_text(text)
    if legacy:
        write_csv(output / 'legacy-RESEARCH-ONLY.csv', list(legacy_rows(rows)), LEGACY_COLUMNS)
    # Dependency-free chart: individual valid observations, not spurious uncertainty.
    for cohort in sorted({r['cohort_id'] for r in rows}):
        subset = [r for r in rows if r['cohort_id'] == cohort and r['quality']['valid']]
        if not subset:
            continue
        maximum = max(r['metrics']['total_cpu_seconds_per_operation'] or 0 for r in subset) or 1
        svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="%d">' % (70 + len(subset)*30),
               '<rect width="100%" height="100%" fill="white"/>',
               '<text x="10" y="25">CPU seconds / operation — individual observations, cohort ' + cohort + '</text>']
        for i, r in enumerate(subset):
            value = r['metrics']['total_cpu_seconds_per_operation']
            y = 55+i*30
            svg += [f'<text x="10" y="{y+15}">{html.escape(r["service"])}</text>',
                    f'<rect x="300" y="{y}" width="{600*value/maximum}" height="20" fill="#287b8e"/>',
                    f'<text x="920" y="{y+15}">{value:.5f}</text>']
        (output / f'cpu-{cohort}.svg').write_text('\n'.join(svg + ['</svg>']))
    (output / 'README.md').write_text(
        '# Generated benchmark outputs\n\n'
        f'{len(rows)} observations; {sum(r["quality"]["valid"] for r in rows)} valid. No benchmark was rerun.\n\n'
        '- presentation.csv: all observations with explicit units in field names and validity.\n'
        '- repeat-statistics.csv: valid runs grouped by cohort/service/use_case; stdev empty for n=1.\n'
        '- ecobenchmark.ipynb: reproducible notebook (pandas/matplotlib); SVG charts require no dependencies.\n'
        '- efootprint.json and readiness.md: provisional service/task resource evidence and blockers, not production factors.\n'
        '- observations.json: normalized evidence with raw SHA-256 provenance.\n\n'
        'CPU includes application plus database. Memory uses timestamp-aligned linear interpolation '
        'on the overlapping sample window; sampled peak is not a guaranteed true peak. CPU spans may '
        'include collection overhead outside k6 timing. Mixed operation means a journey (672 requests '
        'when completed), not an isolated task; in-flight partial journeys can contribute resource usage. '
        'Client latency is not server execution duration. No physical energy values are inferred. '
        'Local/shared-host comparisons are exploratory, not universal software rankings.\n\n'
        'Optional legacy-RESEARCH-ONLY.csv targets the removed pre-Dec-2025 consumer; unsafe per-request '
        'fits and concurrency remain blank. It is deliberately not directly loadable by that consumer.\n')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(output.iterdir()):
            bundle.write(path, output.name + '/' + path.name)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', nargs='+', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--legacy-csv', action='store_true')
    args = parser.parse_args()
    rows = generate(args.inputs, args.output, legacy=args.legacy_csv)
    print(f'Exported {len(rows)} observations ({sum(r["quality"]["valid"] for r in rows)} valid) to {args.output}')


if __name__ == '__main__':
    main()
