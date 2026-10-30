"""Current e-footprint resource observations; never infer task fits from mixed runs."""
from output_data import finite

CONSUMER = 'd69a2ca4842344b9f24bfddf4d7a3a8ed84c8bb6'
UNITS = {'compute_needed': 'cpu_core', 'ram_needed': 'MB_ram',
         'request_duration': 's', 'data_transferred': 'B', 'data_stored': 'B_stored'}
LEGACY_COLUMNS = ['service', 'use_case', 'iterations', 'http_reqs', 'nb_requests_in_parallel',
                  'avg_ram_in_MB', 'avg_cpu_cores', 'avg_ram_per_request_in_MB',
                  'avg_cpu_core_per_request']


def export_profiles(observations):
    profiles = []
    for row in observations:
        blockers = ['No idle CPU/RAM baseline', 'No attributed dynamic RAM and mean concurrency',
                    'No server-side operation duration', 'No durable storage delta',
                    'No calibrated deployment/hardware transfer model']
        if not row['quality']['valid']:
            blockers.append('Failed observation; quarantined')
        if row['workload']['kind'] != 'atomic':
            blockers.append('Mixed or unverified workload; independent task costs are not identifiable')
        profiles.append({'observation_id': row['id'], 'service': row['service'],
                         'job_type': row['workload']['job_type'], 'status': 'blocked',
                         'blockers': blockers, 'job': None, 'service_baseline': None,
                         'observed_resources': row['metrics'], 'energy_status': row['energy']['status'],
                         'provenance': row['provenance']})
    return {'schema_version': 'ecobenchmark.efootprint/v1', 'consumer_commit': CONSUMER,
            'units': UNITS, 'profiles': profiles,
            'note': 'Observations, not loadable Service objects or production coefficients. '
                    'Energy is not required for resource fitting, but simulated energy is never calibration evidence.'}


def build_job(profile, server):
    """Construct a current Job from an explicitly calibrated, sourced quantity profile.

    Exported blocked observations intentionally cannot be passed here. Calibration
    must supply all six quantities in the units above; no one-second defaults.
    """
    if profile.get('status') != 'calibrated' or profile.get('blockers'):
        raise ValueError('Job requires a calibrated profile without blockers')
    if profile.get('simulation') is not False or not profile.get('source', {}).get('link'):
        raise ValueError('Job requires non-simulated, linked calibration provenance')
    quantities = profile.get('job', {})
    for name, unit in UNITS.items():
        quantity = quantities.get(name, {})
        value = finite(quantity.get('value'), name)
        if quantity.get('unit') != unit or value < 0 or (name == 'request_duration' and value <= 0):
            raise ValueError(f'Invalid {name}; expected nonnegative {unit} and positive duration')
    from efootprint.constants.units import u
    from efootprint.abstract_modeling_classes.source_objects import SourceValue
    from efootprint.abstract_modeling_classes.explainable_object_base_class import Source
    from efootprint.core.usage.job import Job
    source = Source(profile['source']['name'], link=profile['source']['link'])
    values = {name: SourceValue(quantities[name]['value'] * u(unit), source=source,
                                confidence='low', comment=profile.get('comment'))
              for name, unit in UNITS.items()}
    return Job(name=profile['name'], server=server, **values)


def legacy_rows(observations):
    # Deliberately no task coefficients: the removed consumer assumed 1 s and used
    # peak RAM/count. Preserve aggregate research fields, leave unsafe fits empty.
    for row in observations:
        if not row['quality']['valid']:
            continue
        m = row['metrics']
        yield dict(zip(LEGACY_COLUMNS, [row['service'], row['use_case'], m['iterations'],
                  m['http_requests'], None, m.get('total_memory_mean_bytes', 0) / 1_000_000,
                  m.get('total_mean_cpu_cores'), None, None]))
