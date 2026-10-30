import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import zipfile

from output_data import resource_metrics, energy_metadata, load_observations
from export_outputs import generate, repeat_statistics
from footprint_output import build_job, export_profiles, UNITS


def resources():
    return [{'timestamp': f'2026-10-30T00:00:{t:02d}+00:00', 'container': role,
             'cpu_seconds': cpu, 'memory_bytes': memory}
            for role, values in [('app', [(0, 10, 1_000_000), (10, 14, 3_000_000)]),
                                 ('db', [(0, 20, 3_000_000), (10, 26, 1_000_000)])]
            for t, cpu, memory in values]


def fixture(root):
    root.mkdir()
    metadata = {'schema_version': 1, 'status': 'succeeded', 'service': 'synthetic-test',
                'run_id': 'test-1', 'execution': {'backend': 'lima'},
                'configuration': {'scenario': 'DATA_LIST', 'duration': '10s'}, 'dataset': 'seed-v1',
                'containers': [{'Id': key, 'Config': {'Labels': {'com.docker.compose.service': role}}}
                               for key, role in [('app', 'application'), ('db', 'database')]]}
    raw = {'metrics': {name: {'values': value} for name, value in {
        'iterations': {'count': 100, 'rate': 10}, 'http_reqs': {'count': 100, 'rate': 10},
        'http_req_failed': {'rate': 0}, 'checks': {'fails': 0},
        'http_req_duration': {'avg': 20, 'p(95)': 30},
        'data_sent': {'count': 2000}, 'data_received': {'count': 3000}}.items()}}
    (root / 'metadata.json').write_text(json.dumps(metadata))
    (root / 'k6-summary.json').write_text(json.dumps(raw))
    (root / 'resources.jsonl').write_text('\n'.join(map(json.dumps, resources())))
    return metadata


class OutputTests(unittest.TestCase):
    def test_cpu_app_plus_database_and_aligned_memory_not_sum_of_peaks(self):
        m = resource_metrics(resources(), {'app': 'application', 'db': 'database'})
        self.assertEqual(m['total_cpu_seconds'], 10)
        self.assertEqual(m['total_mean_cpu_cores'], 1)
        self.assertEqual(m['total_memory_aligned_peak_bytes'], 4_000_000)
        self.assertEqual(m['total_memory_mean_bytes'], 4_000_000)

    def test_resets_disorder_and_missing_role_rejected(self):
        for rows in [resources()[:2], list(reversed(resources())), resources() + [resources()[0]]]:
            with self.assertRaises(ValueError):
                resource_metrics(rows, {'app': 'application', 'db': 'database'})

    def test_energy_cannot_be_promoted_from_simulation_or_naked_joules(self):
        for metadata in [{}, {'energy': {'simulation': True, 'joules': 123}},
                         {'energy': {'available': True, 'joules': 123}}]:
            self.assertIsNone(energy_metadata(metadata)['joules'])
        self.assertEqual(energy_metadata({'simulation': True})['status'], 'simulated')

    def test_end_to_end_without_benchmark_and_duplicate_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); fixture(root / 'raw')
            observations = generate([root / 'raw', root / 'raw'], root / 'out', legacy=True)
            self.assertEqual(len(observations), 1)
            row = observations[0]
            self.assertTrue(row['quality']['valid'])
            self.assertEqual(row['metrics']['total_cpu_seconds_per_operation'], .1)
            self.assertEqual(row['metrics']['request_duration_mean_seconds'], .02)
            self.assertEqual(row['workload']['kind'], 'mixed')  # no declared atomic contract
            self.assertTrue(all(s['n'] == 1 and s['stdev'] is None for s in repeat_statistics(observations)))
            self.assertIsNone(export_profiles(observations)['profiles'][0]['job'])
            with zipfile.ZipFile(root / 'out.zip') as archive:
                self.assertIsNone(archive.testzip())
            notebook = json.loads((root / 'out/ecobenchmark.ipynb').read_text())
            for cell in notebook['cells']:
                if cell['cell_type'] == 'code':
                    compile(''.join(cell['source']), '<notebook>', 'exec')
            with self.assertRaises(FileExistsError):
                generate([root / 'raw'], root / 'out')

    def test_failed_observation_quarantined_and_simulated_energy_unusable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'raw'; metadata = fixture(root)
            metadata.update(status='failed', simulation=True)
            (root / 'metadata.json').write_text(json.dumps(metadata))
            row = load_observations([root])[0]
            self.assertFalse(row['quality']['valid'])
            self.assertIsNone(row['metrics']['total_cpu_seconds_per_operation'])
            self.assertEqual(row['energy']['status'], 'simulated')
            self.assertEqual(repeat_statistics([row]), [])

    def test_atomic_requires_explicit_contract_and_matching_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'raw'; metadata = fixture(root)
            metadata['workload'] = {'kind': 'atomic', 'operations_per_iteration': 1, 'job_type': 'DATA_LIST'}
            (root / 'metadata.json').write_text(json.dumps(metadata))
            self.assertEqual(load_observations([root])[0]['workload']['kind'], 'atomic')
            raw = json.loads((root / 'k6-summary.json').read_text())
            raw['metrics']['http_reqs']['values']['count'] = 200
            (root / 'k6-summary.json').write_text(json.dumps(raw))
            self.assertEqual(load_observations([root])[0]['workload']['kind'], 'mixed')

    def test_sensor_only_input_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'metadata.json').write_text('{"simulation": true}')
            with self.assertRaisesRegex(ValueError, 'Unsupported'):
                load_observations([root])

    def test_source_integrity_and_canonical_schema_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'raw'; metadata = fixture(root)
            schema = {'tables': ['task'], 'columns': ['id']}
            metadata['schema_sha256'] = hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()
            (root / 'metadata.json').write_text(json.dumps(metadata))
            (root / 'schema.json').write_text(json.dumps(schema, indent=2))
            self.assertTrue(load_observations([root])[0]['quality']['valid'])
            (root / 'schema.json').write_text('{}')
            self.assertFalse(load_observations([root])[0]['quality']['valid'])

    def test_job_units_duration_and_provenance_validated_before_import(self):
        base = {'status': 'calibrated', 'blockers': [], 'simulation': False, 'name': 'test',
                'source': {'name': 'test calibration', 'link': 'https://example.org/evidence'},
                'job': {key: {'value': 1, 'unit': unit} for key, unit in UNITS.items()}}
        for key, value in [('compute_needed', {'value': 1, 'unit': 'cpu_seconds'}),
                           ('ram_needed', {'value': 1, 'unit': 'MiB'}),
                           ('request_duration', {'value': 0, 'unit': 's'})]:
            profile = copy.deepcopy(base); profile['job'][key] = value
            with self.assertRaises(ValueError):
                build_job(profile, object())
        with self.assertRaises(ValueError):
            build_job({'status': 'blocked'}, object())
        modules = {key: MagicMock() for key in ['efootprint.constants.units',
                   'efootprint.abstract_modeling_classes.source_objects',
                   'efootprint.abstract_modeling_classes.explainable_object_base_class',
                   'efootprint.core.usage.job']}
        with patch.dict('sys.modules', modules):
            build_job(base, 'server')
            modules['efootprint.core.usage.job'].Job.assert_called_once()
            u = modules['efootprint.constants.units'].u
            self.assertEqual([call.args[0] for call in u.call_args_list], list(UNITS.values()))
