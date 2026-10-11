import copy
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from train_triage_model import synthetic_device, TRAIN_SEED, VALIDATION_SEED, CONTROL_SEED
from triage_model import DEFAULT_MODEL, CLASSES, infer_devices, parameters_sha256


def device(pattern="normal", seed=981273):
    return synthetic_device(random.Random(seed), pattern, "test-device")


def first(value):
    return infer_devices([value])["devices"][0]


class TriageModelTests(unittest.TestCase):
    def test_new_seed_patterns_use_learned_model(self):
        for pattern in CLASSES:
            with self.subTest(pattern=pattern):
                result = first(device(pattern))
                self.assertEqual(result["status"], "ready")
                self.assertEqual(result["pattern"], pattern)
                self.assertTrue(0.60 <= result["score"] <= 1)

    def test_frozen_parameters_are_actually_required(self):
        raw = json.loads(DEFAULT_MODEL.read_text(encoding="utf-8"))
        self.assertGreater(sum(abs(v) for row in raw["weights"] for v in row), 1)
        raw["weights"] = [[0.0]*len(row) for row in raw["weights"]]
        raw["bias"] = [0.0]*4
        raw["parameters_sha256"] = parameters_sha256(raw)
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)/"zero.json"
            p.write_text(json.dumps(raw), encoding="utf-8")
            result = infer_devices([device("persistent_shift")], p)["devices"][0]
        self.assertEqual(result["status"], "insufficient")
        self.assertIsNone(result["pattern"])

    def test_training_and_evaluation_seeds_are_disjoint(self):
        self.assertEqual(len({TRAIN_SEED, VALIDATION_SEED, CONTROL_SEED}), 3)
        raw = json.loads(DEFAULT_MODEL.read_text(encoding="utf-8"))
        self.assertLess(raw["training"]["final_cross_entropy"], raw["training"]["initial_cross_entropy"]*0.1)

    def test_unknown_labels_names_and_topology_do_not_change_result(self):
        original = device("persistent_shift")
        changed = copy.deepcopy(original)
        changed.update(label="normal", scenario="FF-103", pattern="normal", name="Different name", gateway_id="Unknown")
        for point in changed["points"]:
            point["fault_label"] = "healthy"
        self.assertEqual(infer_devices([original]), infer_devices([changed]))

    def test_input_hash_binds_observations_without_mutating_them(self):
        original = device()
        before = copy.deepcopy(original)
        old = infer_devices([original])
        self.assertEqual(original, before)
        changed = copy.deepcopy(original)
        changed["points"][60]["value"] += 0.01
        self.assertNotEqual(old["inputs_sha256"], infer_devices([changed])["inputs_sha256"])

    def test_model_hash_is_hash_of_actual_bytes(self):
        result = infer_devices([device()])
        self.assertEqual(result["model"]["sha256"], hashlib.sha256(DEFAULT_MODEL.read_bytes()).hexdigest())

    def test_different_normal_soil_levels_do_not_become_faults(self):
        for target in (5, 25, 55, 92):
            original = device()
            offset = target-sum(p["value"] for p in original["points"][:48])/48
            for point in original["points"]:
                point["value"] += offset
            self.assertEqual(first(original)["pattern"], "normal")

    def test_short_window_is_insufficient(self):
        original = device()
        original["points"] = original["points"][:48]
        self.assertEqual(first(original)["status"], "insufficient")

    def test_incomplete_history_is_never_normal(self):
        original = device()
        original["points"][12]["value"] = None
        result = first(original)
        self.assertEqual(result["status"], "insufficient")
        self.assertIsNone(result["pattern"])

    def test_intermittent_and_short_missingness_abstain(self):
        for missing in ([55], [55, 57, 71], [70, 71]):
            original = device()
            for index in missing:
                original["points"][index]["value"] = None
            result = first(original)
            self.assertEqual(result["status"], "insufficient")
            self.assertIsNone(result["pattern"])

    def test_all_evaluation_points_missing_is_dropout_not_normal(self):
        original = device()
        for point in original["points"][48:]:
            point["value"] = None
        result = first(original)
        self.assertEqual(result["pattern"], "dropout")
        signals = {s["code"]: s for s in result["signals"]}
        self.assertEqual(signals["detection_observed_points"]["value"], 0)
        self.assertIsNone(signals["median_residual_vwc"]["value"])
        self.assertEqual(signals["trailing_missing_hours"]["value"], 24)
        json.dumps(result, allow_nan=False)

    def test_missing_measurement_field_is_not_explicit_dropout(self):
        original = device()
        for point in original["points"][48:]:
            del point["value"]
        self.assertEqual(first(original)["status"], "unavailable")

    def test_invalid_or_out_of_range_values_are_rejected(self):
        for invalid in (float("nan"), float("inf"), True, "20", -0.1, 100.1):
            original = device()
            original["points"][65]["value"] = invalid
            output = infer_devices([original])
            result = output["devices"][0]
            self.assertEqual(result["status"], "unavailable")
            self.assertIsNone(result["pattern"])
            json.dumps(output, allow_nan=False)

    def test_irregular_duplicate_or_naive_time_is_rejected(self):
        for altered in ("2025-01-01T00:00:00Z", "2025-01-03T12:30:00Z", "2025-01-03T12:00:00"):
            original = device()
            original["points"][60]["t"] = altered
            self.assertEqual(first(original)["status"], "unavailable")

    def test_noisy_history_is_outside_scope(self):
        original = device()
        rng = random.Random(77023)
        for point in original["points"]:
            point["value"] += rng.gauss(0, 5)
        result = first(original)
        self.assertNotEqual(result["status"], "ready")
        self.assertIsNone(result["pattern"])

    def test_flat_history_does_not_claim_healthy_or_stuck(self):
        original = device()
        for point in original["points"]:
            point["value"] = 30.0
        self.assertEqual(first(original)["status"], "insufficient")

    def test_irrigation_and_offset_cannot_be_separated_by_label(self):
        irrigation = device()
        for point in irrigation["points"][48:]:
            point["value"] += 9
        sensor = copy.deepcopy(irrigation)
        irrigation["physical_cause"] = "real_irrigation"
        sensor["physical_cause"] = "sensor_offset"
        a, b = first(irrigation), first(sensor)
        self.assertEqual(a, b)
        self.assertEqual(a["pattern"], "persistent_shift")
        self.assertIn("soil_change_or_sensor_shift_indistinguishable", a["ambiguities"])

    def test_stuck_output_retains_natural_plateau_ambiguity(self):
        result = first(device("stuck"))
        self.assertIn("stable_environment_or_stuck_sensor_indistinguishable", result["ambiguities"])

    def test_signals_have_observation_ranges(self):
        original = device("dropout")
        result = first(original)
        self.assertEqual(len(result["signals"]), 6)
        for signal in result["signals"]:
            self.assertEqual(set(signal), {"code", "value", "unit", "source_range"})
            self.assertEqual(set(signal["source_range"]), {"start", "end"})
            self.assertTrue(signal["source_range"]["start"].endswith("Z"))
        residual = next(s for s in result["signals"] if s["code"] == "median_residual_vwc")
        self.assertEqual(residual["source_range"]["start"], original["points"][0]["t"])
        last = next(s for s in result["signals"] if s["code"] == "trailing_missing_hours")
        self.assertEqual(last["source_range"]["end"], original["points"][-1]["t"])

    def test_missing_or_corrupt_model_fails_without_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"PRIVATE.json"
            result = infer_devices([device()], path)
            self.assertEqual(result["status"], "unavailable")
            path.write_text('{"private_path":"PRIVATE"}', encoding="utf-8")
            result = infer_devices([device()], path)
            self.assertEqual(result["status"], "unavailable")
            self.assertNotIn("PRIVATE", json.dumps(result))

    def test_weight_tampering_without_matching_digest_is_rejected(self):
        raw = json.loads(DEFAULT_MODEL.read_text(encoding="utf-8"))
        raw["weights"][0][0] += 1
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"bad.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            self.assertEqual(infer_devices([device()], path)["status"], "unavailable")

    def test_empty_and_invalid_inputs_are_not_normal(self):
        self.assertEqual(infer_devices([])["status"], "insufficient")
        self.assertEqual(infer_devices(None)["status"], "insufficient")
        self.assertEqual(infer_devices([None])["status"], "unavailable")

    def test_duplicate_id_retains_rejected_device(self):
        original = device()
        output = infer_devices([original, copy.deepcopy(original)])
        self.assertEqual(output["devices"][1]["status"], "unavailable")
        self.assertIsNone(output["devices"][1]["pattern"])

    def test_runtime_does_not_import_numpy_or_torch(self):
        script = "import sys; from triage_model import infer_devices; infer_devices([]); assert 'numpy' not in sys.modules; assert 'torch' not in sys.modules"
        completed = subprocess.run([sys.executable, "-B", "-c", script], cwd=DEFAULT_MODEL.parent.parent, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
