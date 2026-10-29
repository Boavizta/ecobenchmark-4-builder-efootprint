#!/usr/bin/env python3
"""Read-only inventory of service trees on every branch and PR in related repos."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import datetime
import json
from pathlib import Path
import subprocess

REPOSITORIES = (
    'Boavizta/ecobenchmark-applicationweb-backend',
    'Boavizta/ecobenchmark-4-builder-efootprint',
)


def api(path, pages=False):
    args = ['gh', 'api', path]
    if pages:
        args += ['--paginate', '--slurp']
    value = json.loads(subprocess.check_output(args, text=True, timeout=90))
    return [item for page in value for item in page] if pages else value


def tree_services(tree):
    services = {}
    for item in tree:
        parts = item['path'].split('/')
        if len(parts) >= 3 and parts[0] == 'service' and item['type'] == 'blob':
            service = services.setdefault(parts[1], {'files': {}, 'dockerfiles': []})
            relative = '/'.join(parts[2:])
            service['files'][relative] = item['sha']
            if parts[-1].startswith('Dockerfile'):
                service['dockerfiles'].append(relative)
    for service in services.values():
        service['implemented'] = bool(service['dockerfiles'])
    return services


def inventory(repository, output):
    branches = api(f'repos/{repository}/branches?per_page=100', pages=True)
    pulls = api(f'repos/{repository}/pulls?state=all&per_page=100', pages=True)
    refs = [{'kind': 'branch', 'name': b['name'], 'sha': b['commit']['sha']} for b in branches]
    refs += [{'kind': 'pull_request', 'name': str(p['number']), 'title': p['title'],
              'url': p['html_url'], 'state': 'merged' if p['merged_at'] else p['state'],
              'sha': p['head']['sha'], 'base': p['base']['ref']} for p in pulls]

    def fetch(sha):
        try:
            tree = api(f'repos/{repository}/git/trees/{sha}?recursive=1')
            if tree.get('truncated'):
                raise RuntimeError('GitHub truncated the recursive tree')
            return sha, {'services': tree_services(tree['tree']), 'tree': tree}
        except (subprocess.SubprocessError, ValueError, RuntimeError) as error:
            return sha, {'error': str(error)}

    with ThreadPoolExecutor(max_workers=5) as pool:
        trees = dict(pool.map(fetch, sorted({ref['sha'] for ref in refs})))
    # PR file lists cover deleted fork heads as well as changes outside service/.
    def files(pull):
        return str(pull['number']), api(f"repos/{repository}/pulls/{pull['number']}/files?per_page=100", pages=True)
    with ThreadPoolExecutor(max_workers=5) as pool:
        pull_files = dict(pool.map(files, pulls))
    raw = {'repository': repository, 'branches': branches, 'pull_requests': pulls,
           'refs': refs, 'trees': trees, 'pull_request_files': pull_files}
    (output / (repository.split('/')[1] + '.json')).write_text(json.dumps(raw, indent=2) + '\n')
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    reports = [inventory(repo, args.output) for repo in REPOSITORIES]
    lines = ['# Upstream branch and PR service inventory', '',
             'Fetched at ' + datetime.datetime.now(datetime.timezone.utc).isoformat(), '',
             'Read-only scan. A Dockerfile is an implementation candidate, not proof it builds or shares benchmark scope.', '']
    for report in reports:
        lines += [f"## {report['repository']}", '',
                  f"{len(report['branches'])} branches; {len(report['pull_requests'])} PRs (all states).", '',
                  '| Ref | State | Commit | Implementation candidates |',
                  '| --- | --- | --- | --- |']
        for ref in report['refs']:
            tree = report['trees'][ref['sha']]
            names = [name for name, value in tree.get('services', {}).items() if value['implemented']]
            label = ref['name'] if ref['kind'] == 'branch' else f"[PR #{ref['name']}]({ref['url']})"
            lines.append(f"| {label} | {ref.get('state', 'branch')} | {ref['sha'][:12]} | "
                         + (', '.join(sorted(names)) or tree.get('error', 'none')) + ' |')
        lines.append('')
    (args.output / 'inventory.md').write_text('\n'.join(lines))
    for report in reports:
        names = sorted({name for tree in report['trees'].values()
                        for name, service in tree.get('services', {}).items() if service['implemented']})
        print(report['repository'], f"{len(report['branches'])} branches, {len(report['pull_requests'])} PRs")
        print('Implementation candidates:', ', '.join(names))
        for sha, tree in report['trees'].items():
            if 'error' in tree:
                print('UNREADABLE TREE:', sha, tree['error'])


if __name__ == '__main__':
    main()
