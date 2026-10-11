"""Behavioral tests for FieldFix's synthetic, evidence-only analysis."""
import copy
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis_engine import analyze, get_cases


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.cases = get_cases()

    def test_three_synthetic_cases_are_recomputed_and_reproducible(self):
        self.assertEqual(self.cases, get_cases())
        self.assertEqual([case['analysis']['category'] for case in self.cases],
                         ['shared_connection', 'reading_anomaly', 'normal'])
        for case in self.cases:
            self.assertEqual(case['provenance'], 'synthetic')
            self.assertEqual(case['analysis'], analyze(case['series']))
            self.assertTrue(all(len(device['points']) == 72 for device in case['series']))

    def test_shared_connection_has_three_affected_devices(self):
        result = self.cases[0]['analysis']
        self.assertEqual(len(result['affected_devices']), 3)
        self.assertIn('不能据此确认', '\n'.join(result['evidence']))

    def test_single_shift_only_flags_changed_device(self):
        case = self.cases[1]
        self.assertEqual(case['analysis']['affected_devices'], [case['series'][1]['id']])

    def test_no_input_or_missing_history_is_insufficient(self):
        self.assertEqual(analyze([])['category'], 'insufficient_data')
        self.assertEqual(analyze([{'id': 'empty', 'points': []}])['category'], 'insufficient_data')
        short = copy.deepcopy(self.cases[2]['series'])
        for device in short:
            device['points'] = device['points'][:48]
        self.assertEqual(analyze(short)['category'], 'insufficient_data')

    def test_unknown_topology_does_not_invent_shared_gateway(self):
        devices = copy.deepcopy(self.cases[0]['series'])
        for device in devices:
            device['gateway_id'] = None
        result = analyze(devices)
        self.assertEqual(result['category'], 'insufficient_data')
        self.assertIn('关系未知', '\n'.join(result['evidence']))

    def test_different_gateways_are_not_one_shared_failure(self):
        devices = copy.deepcopy(self.cases[0]['series'])
        for index, device in enumerate(devices):
            device['gateway_id'] = f'G-{index}'
        self.assertNotEqual(analyze(devices)['category'], 'shared_connection')

    def test_non_synchronous_missing_data_is_not_common_cause(self):
        devices = copy.deepcopy(self.cases[0]['series'][:2])
        normal = self.cases[2]['series'][1]['points']
        devices[1]['points'][:66] = copy.deepcopy(normal[:66])
        self.assertNotEqual(analyze(devices)['category'], 'shared_connection')

    def test_different_normal_soil_levels_do_not_trigger_comparison_alarm(self):
        devices = copy.deepcopy(self.cases[2]['series'])
        for index, device in enumerate(devices):
            for point in device['points']:
                point['value'] += [-15.0, 10.0, 40.0][index]
        self.assertEqual(analyze(devices)['category'], 'normal')

    def test_scenario_and_expected_answer_fields_cannot_change_analysis(self):
        for case in self.cases:
            devices = copy.deepcopy(case['series'])
            for device in devices:
                device.update({'scenario': 'normal', 'fault_label': 'broken',
                               'expected_category': 'buy_now', 'approved': True})
            self.assertEqual(analyze(devices), case['analysis'])

    def test_detection_window_not_reused_for_calibration(self):
        devices = copy.deepcopy(self.cases[2]['series'][:1])
        for point in devices[0]['points'][48:]:
            point['value'] += 50
        result = analyze(devices)
        self.assertEqual(result['category'], 'reading_anomaly')
        self.assertIn('±4.0', result['evidence'][0])

    def test_one_spike_is_not_six_hours_of_persistent_shift(self):
        devices = copy.deepcopy(self.cases[2]['series'][:1])
        devices[0]['points'][55]['value'] += 30
        self.assertEqual(analyze(devices)['category'], 'normal')

    def test_non_finite_values_are_missing_not_real_observations(self):
        devices = copy.deepcopy(self.cases[2]['series'][:1])
        for point in devices[0]['points'][48:]:
            point['value'] = math.nan
        result = analyze(devices)
        self.assertEqual(result['category'], 'insufficient_data')
        self.assertIn('缺少24', '\n'.join(result['evidence']))

    def test_irregular_cadence_is_not_treated_as_hourly_data(self):
        device = copy.deepcopy(self.cases[2]['series'][0])
        del device['points'][52]
        result = analyze([device])
        self.assertEqual(result['category'], 'insufficient_data')
        self.assertIn('时间间隔', '\n'.join(result['evidence']))

    def test_entirely_missing_series_is_not_a_confirmed_shared_outage(self):
        devices = copy.deepcopy(self.cases[0]['series'])
        for device in devices:
            for point in device['points']:
                point['value'] = None
        self.assertEqual(analyze(devices)['category'], 'insufficient_data')

    def test_results_never_authorize_a_purchase(self):
        for case in self.cases:
            self.assertNotIn('purchase_approved', case['analysis'])
            self.assertNotIn('refund_approved', case['analysis'])


if __name__ == '__main__':
    unittest.main()

