"""Independent numeric and missing-evidence controls for demo recovery."""
import copy
import json
import math
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from recovery import _evaluate_observations, evaluate_recovery


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.points = evaluate_recovery("recovered")["observations"]

    def check_by_code(self, result, code):
        return next(item for item in result["checks"] if item["code"] == code)

    def test_three_reproducible_synthetic_scenarios(self):
        for scenario, expected, count in [("recovered", "pass", 24),
                                           ("still_faulty", "fail", 24),
                                           ("insufficient", "insufficient", 6)]:
            with self.subTest(scenario=scenario):
                result = evaluate_recovery(scenario)
                self.assertEqual(result, evaluate_recovery(scenario))
                self.assertEqual(result["status"], expected)
                self.assertEqual(result["sample_count"], count)
                self.assertEqual(result["source"], "synthetic_fixture")
                self.assertEqual(len(result["observations"]), 24)
                json.dumps(result, allow_nan=False)

    def test_recovered_metrics_come_from_numeric_pairs(self):
        result = evaluate_recovery("recovered")
        errors = [abs(point["sensor"] - point["reference"]) for point in self.points]
        self.assertAlmostEqual(result["metrics"]["mean_absolute_error"], sum(errors) / len(errors), places=4)
        self.assertAlmostEqual(result["metrics"]["max_absolute_error"], max(errors), places=4)
        self.assertTrue(all(item["status"] == "pass" for item in result["checks"]))

    def test_connected_stuck_fixture_does_not_pass(self):
        result = evaluate_recovery("still_faulty")
        self.assertEqual(self.check_by_code(result, "link_success_ratio")["status"], "pass")
        self.assertEqual(self.check_by_code(result, "sensor_variation")["status"], "fail")
        self.assertEqual(result["metrics"]["sensor_range"], 0.0)
        self.assertGreater(result["metrics"]["reference_range"], 1.0)

    def test_stuck_check_is_independent_of_large_residual(self):
        points = copy.deepcopy(self.points)
        for index, point in enumerate(points):
            point["reference"] = 40 + index * 1.2 / 23
            point["sensor"] = 40.6
        result = _evaluate_observations(points)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(self.check_by_code(result, "mean_absolute_error")["status"], "pass")
        self.assertEqual(self.check_by_code(result, "max_absolute_error")["status"], "pass")
        self.assertEqual(self.check_by_code(result, "sensor_variation")["status"], "fail")

    def test_persistent_bias_fails_mean_even_below_peak_limit(self):
        points = copy.deepcopy(self.points)
        for point in points:
            point["sensor"] = point["reference"] + 2
        result = _evaluate_observations(points)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["metrics"]["mean_absolute_error"], 2.0)
        self.assertEqual(self.check_by_code(result, "max_absolute_error")["status"], "pass")
        self.assertEqual(self.check_by_code(result, "sensor_variation")["status"], "pass")

    def test_one_large_spike_fails_peak_even_with_low_mean(self):
        points = copy.deepcopy(self.points)
        for point in points:
            point["sensor"] = point["reference"]
        points[12]["sensor"] += 4
        result = _evaluate_observations(points)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(self.check_by_code(result, "mean_absolute_error")["status"], "pass")
        self.assertEqual(self.check_by_code(result, "max_absolute_error")["status"], "fail")

    def test_link_failures_are_independent_of_good_readings(self):
        points = copy.deepcopy(self.points)
        for point in points[:3]:
            point["link_up"] = False
        result = _evaluate_observations(points)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["sample_count"], 21)
        self.assertEqual(result["metrics"]["link_success_ratio"], 0.875)
        self.assertEqual(self.check_by_code(result, "mean_absolute_error")["status"], "pass")

    def test_fully_observed_outage_fails_without_inventing_numeric_evidence(self):
        points = copy.deepcopy(self.points)
        for point in points:
            point["link_up"] = False
        result = _evaluate_observations(points)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["sample_count"], 0)
        self.assertIsNone(result["metrics"]["mean_absolute_error"])
        self.assertEqual(self.check_by_code(result, "mean_absolute_error")["status"], "insufficient")

    def test_missing_evidence_does_not_become_zero_error_pass(self):
        result = evaluate_recovery("insufficient")
        self.assertEqual(result["metrics"]["link_unknown_count"], 18)
        self.assertEqual(self.check_by_code(result, "mean_absolute_error")["status"], "insufficient")
        self.assertEqual(_evaluate_observations([])["status"], "insufficient")
        points = copy.deepcopy(self.points)
        for point in points:
            point["sensor"] = None
        result = _evaluate_observations(points)
        self.assertEqual(result["status"], "insufficient")
        self.assertIsNone(result["metrics"]["mean_absolute_error"])

    def test_perfect_but_flat_reference_is_insufficient_to_exclude_stuck(self):
        points = copy.deepcopy(self.points)
        for point in points:
            point["sensor"] = point["reference"] = 32.0
        result = _evaluate_observations(points)
        self.assertEqual(result["status"], "insufficient")
        self.assertEqual(result["metrics"]["mean_absolute_error"], 0.0)
        self.assertEqual(self.check_by_code(result, "sensor_variation")["status"], "insufficient")

    def test_insufficient_known_links_cannot_pass(self):
        points = copy.deepcopy(self.points)
        for point in points[:3]:
            point["link_up"] = None
        result = _evaluate_observations(points)
        self.assertEqual(result["sample_count"], 21)
        self.assertEqual(result["status"], "insufficient")
        self.assertEqual(self.check_by_code(result, "link_success_ratio")["status"], "insufficient")

    def test_invalid_or_duplicate_time_does_not_count_as_a_valid_window(self):
        for value in ["not-a-time", self.points[0]["t"], "2026-10-08T01:00:00"]:
            points = copy.deepcopy(self.points)
            points[1]["t"] = value
            result = _evaluate_observations(points)
            self.assertEqual(result["status"], "insufficient")
            self.assertEqual(self.check_by_code(result, "observation_window")["status"], "insufficient")

    def test_nonfinite_and_boolean_readings_are_missing_and_json_safe(self):
        points = copy.deepcopy(self.points)
        for index, value in enumerate([math.nan, math.inf, -math.inf, True, False, "32", 10 ** 1000]):
            points[index]["sensor"] = value
        result = _evaluate_observations(points)
        self.assertEqual(result["sample_count"], 17)
        self.assertEqual(result["status"], "insufficient")
        json.dumps(result, allow_nan=False)

    def test_scenario_labels_do_not_override_evidence_evaluation(self):
        bad_points = evaluate_recovery("still_faulty")["observations"]
        for point in bad_points:
            point.update({"expected_status": "pass", "scenario": "recovered", "paid": True})
        with patch("recovery._fixture_observations", return_value=bad_points):
            self.assertEqual(evaluate_recovery("recovered")["status"], "fail")
        with patch("recovery._fixture_observations", return_value=self.points):
            self.assertEqual(evaluate_recovery("still_faulty")["status"], "pass")

    def test_threshold_boundary_is_inclusive_for_mean_error(self):
        points = copy.deepcopy(self.points)
        for point in points:
            point["sensor"] = point["reference"] + 1.5
        self.assertEqual(_evaluate_observations(points)["status"], "pass")
        for point in points:
            point["sensor"] += 0.01
        self.assertEqual(_evaluate_observations(points)["status"], "fail")

    def test_outputs_are_fresh_and_inputs_are_not_mutated(self):
        points = copy.deepcopy(self.points)
        original = copy.deepcopy(points)
        _evaluate_observations(points)
        self.assertEqual(points, original)
        result = evaluate_recovery("recovered")
        result["observations"][0]["sensor"] = 999
        result["metrics"]["thresholds"]["max_absolute_error"] = 999
        self.assertEqual(evaluate_recovery("recovered")["observations"], self.points)
        self.assertEqual(evaluate_recovery("recovered")["metrics"]["thresholds"]["max_absolute_error"], 3.0)

    def test_invalid_scenarios_are_rejected_and_no_payment_permission_is_returned(self):
        for scenario in ["", "PASS", "paid", None, 1, []]:
            with self.subTest(scenario=scenario), self.assertRaisesRegex(ValueError, "Unknown recovery scenario"):
                evaluate_recovery(scenario)
        self.assertEqual(set(evaluate_recovery("recovered")), {
            "scenario", "source", "status", "sample_count", "metrics", "checks", "observations", "explanation"})


if __name__ == "__main__":
    unittest.main()
