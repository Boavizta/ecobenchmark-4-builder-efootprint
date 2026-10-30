#!/usr/bin/env python3
"""Pinned Scaphandre collector: real-host preflight and explicitly synthetic RAPL demo."""
import argparse
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import uuid

RELEASE = '1.0.3'
REVISION = 'b64443c447e24f25947111ec8611449f213eb0a5'
IMAGE = ('hubblo/scaphandre:1.0.3@sha256:'
         'cd1d8c27d359d0e5add0cf8bcced5ca2bf6699aa212b03999a6a9b131fdc4416')
SIMULATION_WARNING = ('SIMULATED ENERGY: generated RAPL counters, not hardware energy. '
                      'Not suitable for comparing services or e-footprint calibration.')


def command(args, timeout=120):
    return subprocess.check_output(args, text=True, timeout=timeout).strip()


def preflight():
    """Read-only probe on the actual Linux target, not on its Docker client host."""
    result = {'collector': 'scaphandre', 'release': RELEASE, 'system': platform.system(),
              'architecture': platform.machine(), 'available': False, 'joules': None,
              'sensor_files': []}
    if result['system'] != 'Linux' or result['architecture'] not in ('x86_64', 'amd64'):
        result['reason'] = 'Requires a compatible Linux x86-64 target exposing readable RAPL counters.'
        return result
    root = Path('/sys/class/powercap')
    for path in root.glob('intel-rapl:*/energy_uj'):
        try:
            value = int(path.read_text().strip())
            if value >= 0:
                result['sensor_files'].append(str(path))
        except (OSError, ValueError):
            pass
    result['available'] = bool(result['sensor_files'])
    result['reason'] = ('Readable counters found; this is capability detection, not an energy measurement. '
                        'Check sensor domains and virtualization provenance before collecting.' if result['available']
                        else 'No readable RAPL counters; unavailable is not zero joules.')
    return result


def summarize_reports(reports, *, simulation=True):
    """Scaphandre JSON consumption is in microwatts; never sum nested domains twice."""
    samples = []
    placeholders = 0
    for report in reports:
        host = report['host']
        watts = float(host['consumption']) / 1_000_000
        timestamp = float(host['timestamp'])
        if not math.isfinite(watts) or not math.isfinite(timestamp) or watts < 0:
            raise ValueError('Invalid Scaphandre power/timestamp value')
        # Upstream emits an all-zero, socket-less placeholder before its first delta.
        if not report.get('sockets') and watts == 0:
            placeholders += 1
            continue
        if not report.get('sockets'):
            raise ValueError('Host power is present without sensor socket evidence')
        if samples and timestamp <= samples[-1][0]:
            raise ValueError('Scaphandre timestamps must increase')
        samples.append((timestamp, watts))
    if len(samples) < 2:
        raise ValueError('Insufficient sensor samples; energy is unavailable, not zero')
    # Each power value is derived from the preceding counter interval.
    joules = sum((current[0] - previous[0]) * current[1]
                 for previous, current in zip(samples, samples[1:]))
    covered = samples[-1][0] - samples[0][0]
    return {'collector': 'scaphandre', 'release': RELEASE, 'simulation': simulation,
            'measured_energy_available': not simulation,
            'joules': None if simulation else joules,
            'simulated_joules': joules if simulation else None,
            'covered_seconds': covered, 'sample_count': len(samples), 'warmup_placeholders': placeholders,
            'mean_power_watts': joules / covered, 'process_attribution_included': False,
            'scope': 'Scaphandre host aggregate (normally RAPL package + DRAM, or PSYS); not whole-machine wall power.',
            'warning': SIMULATION_WARNING if simulation else
                       'RAPL-domain energy only. Process/container allocations are estimates, not separate meters.'}


def atomic_counter(path, value):
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(str(value) + '\n')
    temporary.replace(path)


def make_fixture(directory, cpus):
    root = directory / 'powercap'
    counters = []
    for name, label, watts in [('intel-rapl:0', 'package-0', 40), ('intel-rapl:0:0', 'dram', 10)]:
        domain = root / name
        domain.mkdir(parents=True)
        (domain / 'name').write_text(label + '\n')
        (domain / 'max_energy_range_uj').write_text('1000000000000\n')
        counter = domain / 'energy_uj'
        atomic_counter(counter, 1_000_000_000)
        counters.append((counter, watts))
    # amd64 emulation on Apple Silicon still sees an ARM kernel's /proc/cpuinfo.
    # Supply explicitly FAKE topology only inside this isolated simulation container.
    cpuinfo = directory / 'cpuinfo'
    cpuinfo.write_text('\n\n'.join(
        f'processor\t: {i}\nvendor_id\t: GenuineIntel\nphysical id\t: 0\n'
        f'core id\t: {i}\ncpu cores\t: {cpus}\nsiblings\t: {cpus}\n'
        'model name\t: SIMULATED Intel topology - NOT real hardware\ncpu MHz\t: 2000.000\n'
        for i in range(cpus)) + '\n')
    # procfs 0.15 cannot parse Docker Desktop module refcounts printed as '-'.
    # An empty module inventory is a valid synthetic VM fixture (no real modules).
    (directory / 'modules').write_text('')
    return counters, cpuinfo


def image_metadata():
    command(['docker', 'pull', '--platform', 'linux/amd64', IMAGE], timeout=180)
    details = json.loads(command(['docker', 'image', 'inspect', IMAGE]))[0]
    labels = details['Config'].get('Labels', {})
    if labels.get('org.opencontainers.image.revision') != REVISION or labels.get('org.opencontainers.image.version') != RELEASE:
        raise RuntimeError('Scaphandre image provenance does not match the pinned release')
    binary_version = command(['docker', 'run', '--rm', '--platform', 'linux/amd64',
                              '--network', 'none', IMAGE, '--version'])
    return {'release': RELEASE, 'source_revision': REVISION, 'image': IMAGE,
            'image_id': details['Id'], 'architecture': details['Architecture'],
            'binary_version_string': binary_version,
            'version_note': 'Upstream v1.0.3 retains Cargo package version 1.0.2; OCI release/revision identify the release.'}


def simulation_image(output):
    context = Path(__file__).parent / 'scaphandre_sim'
    tag = 'ecobenchmark-scaphandre-simulation:1.0.3'
    with (output / 'simulation-build.log').open('w') as log:
        subprocess.run(['docker', 'build', '--platform', 'linux/amd64', '-t', tag, str(context)],
                       stdout=log, stderr=subprocess.STDOUT, check=True, timeout=600)
    return command(['docker', 'image', 'inspect', '-f', '{{.Id}}', tag])


def simulate(output, duration):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    metadata = {'simulation': True, 'measured_energy_available': False, 'joules': None,
                'warning': SIMULATION_WARNING, 'status': 'failed',
                'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'duration_seconds': duration, 'expected_package_watts': 40, 'expected_dram_watts': 10,
                'synthetic_proc_files': ['/proc/cpuinfo', '/proc/modules'],
                'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'controller_host_preflight': preflight()}
    name = 'ecobench-scaphandre-sim-' + uuid.uuid4().hex[:10]
    try:
        metadata['collector'] = image_metadata()
        image = simulation_image(output)
        metadata['simulation_image_id'] = image
        metadata['simulation_read_adapter_sha256'] = hashlib.sha256(
            (Path(__file__).parent / 'scaphandre_sim/fixture_reads.c').read_bytes()).hexdigest()
        metadata['simulation_generator_sha256'] = hashlib.sha256(
            (Path(__file__).parent / 'scaphandre_sim/generate.py').read_bytes()).hexdigest()
        engine = json.loads(command(['docker', 'info', '--format', '{{json .}}']))
        metadata['docker_engine_architecture'] = engine['Architecture']
        metadata['execution'] = 'linux/amd64 container; synthetic CPU topology and RAPL counters'
        make_fixture(output, int(engine['NCPU']))
        args = ['docker', 'run', '--rm', '--name', name, '--platform', 'linux/amd64',
                '--network', 'none', '--read-only', '--cap-drop', 'ALL',
                '--tmpfs', '/tmp:rw,nosuid,nodev,size=64m,mode=1777',
                '--security-opt', 'no-new-privileges', '--user', f'{os.getuid()}:{os.getgid()}',
                '--entrypoint', 'python3',
                '--mount', f'type=bind,src={output},dst=/simulation,readonly',
                '--mount', f'type=bind,src={output},dst=/output', image,
                '/opt/scaphandre-simulation/generate.py', str(duration)]
        with (output / 'collector.log').open('w') as log:
            subprocess.run(args, stdout=log, stderr=subprocess.STDOUT, timeout=duration + 60, check=True)
        reports = json.loads((output / 'scaphandre.json').read_text())
        summary = summarize_reports(reports, simulation=True)
        summary['expected_power_watts'] = 50
        summary['relative_error'] = abs(summary['mean_power_watts'] - 50) / 50
        (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        if summary['relative_error'] > 0.15:
            raise RuntimeError('Exported power differs from the synthetic input by more than 15%')
        metadata['status'] = 'passed'
        print(json.dumps(summary, indent=2))
    except BaseException as error:
        metadata['error'] = str(error)
        raise
    finally:
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True)
        (output / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor', help='Read-only real-host capability probe (does not measure energy)')
    simulation = sub.add_parser('simulate', help='Run the real x86 Scaphandre exporter against fake RAPL counters')
    simulation.add_argument('--output', type=Path, required=True)
    simulation.add_argument('--duration', type=int, default=15)
    args = parser.parse_args()
    if args.command == 'doctor':
        print(json.dumps(preflight(), indent=2))
    else:
        if args.duration < 5:
            parser.error('Simulation requires at least 5 seconds for multiple counter samples')
        simulate(args.output, args.duration)


if __name__ == '__main__':
    main()
