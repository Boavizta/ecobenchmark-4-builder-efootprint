import unittest
from pathlib import Path
import tempfile

import scaphandre


def report(timestamp, microwatts, sockets=None):
    return {'host': {'timestamp': timestamp, 'consumption': microwatts},
            'sockets': [{'id': 0, 'consumption': microwatts}] if sockets is None else sockets,
            'consumers': []}


class ScaphandreTests(unittest.TestCase):
    def test_fixture_contains_only_explicitly_synthetic_topology_and_counters(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            counters, cpuinfo = scaphandre.make_fixture(root, 2)
            self.assertEqual([watts for _, watts in counters], [40, 10])
            self.assertTrue(all(path.read_text().strip() == '1000000000' for path, _ in counters))
            self.assertIn('SIMULATED Intel topology', cpuinfo.read_text())
            self.assertEqual((root / 'modules').read_text(), '')

    def test_microwatts_are_converted_to_watts_without_double_counting_sockets(self):
        result = scaphandre.summarize_reports([report(100, 50_000_000), report(110, 50_000_000)])
        self.assertEqual(result['simulated_joules'], 500)
        self.assertEqual(result['mean_power_watts'], 50)

    def test_simulation_never_populates_measured_joules(self):
        result = scaphandre.summarize_reports([report(100, 50_000_000), report(110, 50_000_000)])
        self.assertTrue(result['simulation'])
        self.assertFalse(result['measured_energy_available'])
        self.assertIsNone(result['joules'])

    def test_no_sensor_data_is_unavailable_not_zero_energy(self):
        with self.assertRaisesRegex(ValueError, 'unavailable, not zero'):
            scaphandre.summarize_reports([report(100, 0, []), report(110, 0, [])])

    def test_initial_placeholder_is_not_integrated_as_real_sensor_data(self):
        result = scaphandre.summarize_reports([
            report(99, 0, []), report(100, 50_000_000), report(110, 50_000_000)])
        self.assertEqual(result['covered_seconds'], 10)
        self.assertEqual(result['warmup_placeholders'], 1)

    def test_invalid_power_or_nonmonotonic_time_is_rejected(self):
        for reports in [
            [report(100, -1), report(110, 10)],
            [report(100, float('nan')), report(110, 10)],
            [report(100, 10), report(100, 10)],
            [report(100, 10), report(99, 10)],
        ]:
            with self.assertRaises(ValueError):
                scaphandre.summarize_reports(reports)
