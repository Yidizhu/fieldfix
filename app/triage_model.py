"""Frozen synthetic-pattern model; no hardware diagnosis or payment authority.

The web inference path is standard-library only. Labels and scenario metadata
are never read. The fixed contract is 48 historical plus 24 evaluation hours.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from statistics import median

MODEL_ID = "fieldfix-triage-synthetic-v1"
CLASSES = ["normal", "persistent_shift", "stuck", "dropout"]
FEATURE_ORDER = [
    "absolute_median_residual", "residual_mad", "maximum_absolute_residual",
    "persistent_fraction", "flat_duration_fraction", "detection_range",
    "historical_range", "observed_fraction", "trailing_missing_fraction",
    "median_absolute_detection_step", "historical_noise", "absolute_residual_trend",
]
LIMITATIONS = [
    "trained_on_self_generated_synthetic_patterns_only",
    "pattern_score_not_accuracy_or_fault_probability",
    "no_real_hardware_validation",
    "soil_change_and_sensor_shift_can_be_observationally_identical",
    "stable_environment_and_stuck_sensor_can_be_observationally_identical",
    "missing_telemetry_does_not_identify_connection_or_hardware_cause",
    "fixed_48_hour_history_and_24_hour_evaluation",
    "hourly_vwc_percentage_points_only",
    "no_research_data_or_cloud_api_used",
    "no_purchase_or_payment_authority",
]
DEFAULT_MODEL = Path(__file__).resolve().parent / "models" / "triage-model-v1.json"


class InputError(ValueError):
    def __init__(self, code, status="unavailable"):
        self.code, self.status = code, status
        super().__init__(code)


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _canonical_bytes(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def parameters_sha256(model):
    return hashlib.sha256(_canonical_bytes({
        key: model[key] for key in ("feature_order", "classes", "normalization", "weights", "bias")
    })).hexdigest()


def _input_hash(devices):
    """Bind only consumed fields. Metadata/labels cannot affect this hash."""
    try:
        projected = []
        for device in devices:
            if not isinstance(device, dict):
                return None
            points = device.get("points")
            selected = ([{"t": p.get("t"), "value": p.get("value")} if isinstance(p, dict) else p
                         for p in points] if isinstance(points, list) else points)
            projected.append({"id": device.get("id"), "points": selected})
        # Nonfinite JSON constants are fingerprinted but still rejected by the
        # input validator; they never appear as numeric output.
        data = json.dumps(projected, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=True)
        return hashlib.sha256(data.encode("utf-8")).hexdigest()
    except (TypeError, ValueError, OverflowError, RecursionError):
        return None


def _range(times):
    return {"start": times[0], "end": times[-1]}


def extract_features(device):
    """Validate a single trace and derive label-free, level-invariant features."""
    points = device.get("points")
    if not isinstance(points, list):
        raise InputError("invalid_points")
    if len(points) < 72:
        raise InputError("need_72_hourly_points", "insufficient")
    if len(points) != 72:
        raise InputError("unsupported_window_length")
    times, instants, values = [], [], []
    for point in points:
        if not isinstance(point, dict) or not isinstance(point.get("t"), str):
            raise InputError("invalid_timestamp")
        try:
            instant = datetime.fromisoformat(point["t"].replace("Z", "+00:00"))
            if instant.utcoffset() is None:
                raise InputError("timezone_required")
            instant = instant.astimezone(timezone.utc)
        except (ValueError, OverflowError):
            raise InputError("invalid_timestamp") from None
        if "value" not in point:
            raise InputError("missing_measurement_field")
        value = point["value"]
        if value is not None:
            if not _finite(value):
                raise InputError("invalid_measurement")
            if not 0 <= value <= 100:
                raise InputError("outside_vwc_range")
            value = float(value)
        times.append(instant.isoformat().replace("+00:00", "Z"))
        instants.append(instant)
        values.append(value)
    if any((b-a).total_seconds() != 3600 for a, b in zip(instants, instants[1:])):
        raise InputError("non_hourly_or_unordered_timestamps")
    history, event = values[:48], values[48:]
    if any(v is None for v in history):
        raise InputError("incomplete_history", "insufficient")
    historical_range = max(history) - min(history)
    if historical_range < 0.1:
        raise InputError("uninformative_history", "insufficient")
    noise = median(abs(history[i+24]-history[i]) for i in range(24))
    if noise > 1.5:
        raise InputError("historical_noise_outside_training_scope")
    trailing = 0
    for value in reversed(event):
        if value is not None:
            break
        trailing += 1
    missing = sum(v is None for v in event)
    if missing and (missing != trailing or trailing < 6):
        raise InputError("unsupported_missing_pattern", "insufficient")
    reference = [(history[i]+history[i+24])/2 for i in range(24)]
    residuals = [v-reference[i] for i, v in enumerate(event) if v is not None]
    observed = [v for v in event if v is not None]
    centre = median(residuals) if residuals else 0.0
    residual_mad = median(abs(v-centre) for v in residuals) if residuals else 0.0
    maximum = max(map(abs, residuals)) if residuals else 0.0
    run, flat_duration = 0, 0
    deltas = []
    for previous, current in zip(event, event[1:]):
        if previous is not None and current is not None:
            step = abs(current-previous)
            deltas.append(step)
            run = run+1 if step <= 1e-8 else 0
            flat_duration = max(flat_duration, run)
        else:
            run = 0
    residual_trend = (median(residuals[-6:])-median(residuals[:6])) if len(residuals) >= 12 else 0.0
    persistent = (sum(abs(v) > 2.0 for v in residuals)/len(residuals)) if residuals else 0.0
    features = [
        abs(centre), residual_mad, maximum, persistent, flat_duration/23,
        max(observed)-min(observed) if observed else 0.0, historical_range,
        len(observed)/24, trailing/24, median(deltas) if deltas else 0.0,
        noise, abs(residual_trend),
    ]
    signals = [
        {"code": "calibration_points", "value": 48, "unit": "count", "source_range": _range(times[:48])},
        {"code": "detection_observed_points", "value": len(observed), "unit": "count", "source_range": _range(times[48:])},
        {"code": "median_residual_vwc", "value": centre if residuals else None, "unit": "percentage_points", "source_range": _range(times)},
        {"code": "flat_duration_hours", "value": flat_duration, "unit": "hours", "source_range": _range(times[48:])},
        {"code": "trailing_missing_hours", "value": trailing, "unit": "hours", "source_range": _range(times[-trailing:] if trailing else times[48:])},
        {"code": "historical_noise_vwc", "value": noise, "unit": "percentage_points", "source_range": _range(times[:48])},
    ]
    return features, signals


def _load_model(path):
    payload = Path(path).read_bytes()
    if len(payload) > 250_000:
        raise ValueError("oversized_model")
    model = json.loads(payload)
    if model.get("id") != MODEL_ID or model.get("version") != 1 or model.get("algorithm") != "multinomial_logistic_regression":
        raise ValueError("unsupported_model")
    if model.get("training_data") != "synthetic" or model.get("feature_order") != FEATURE_ORDER or model.get("classes") != CLASSES:
        raise ValueError("unsupported_model")
    if model.get("parameters_sha256") != parameters_sha256(model):
        raise ValueError("parameters_hash_mismatch")
    n = len(FEATURE_ORDER)
    norm = model["normalization"]
    for name in ("mean", "scale", "lower", "upper"):
        if len(norm[name]) != n or any(not _finite(v) for v in norm[name]):
            raise ValueError("invalid_normalization")
    if any(v <= 0 for v in norm["scale"]) or any(lo >= hi for lo, hi in zip(norm["lower"], norm["upper"])):
        raise ValueError("invalid_normalization")
    if len(model["weights"]) != 4 or any(len(row) != n or any(not _finite(v) for v in row) for row in model["weights"]):
        raise ValueError("invalid_weights")
    if len(model["bias"]) != 4 or any(not _finite(v) for v in model["bias"]):
        raise ValueError("invalid_bias")
    policy = model["abstention"]
    if policy != {"minimum_score": 0.60, "minimum_margin": 0.15}:
        raise ValueError("unsupported_abstention_policy")
    if not isinstance(model["training_seed"], int) or not isinstance(model["validation_seed"], int) or model["training_seed"] == model["validation_seed"]:
        raise ValueError("invalid_split")
    return model, hashlib.sha256(payload).hexdigest()


def _predict(features, model):
    norm = model["normalization"]
    if any(value < lower or value > upper for value, lower, upper in zip(features, norm["lower"], norm["upper"])):
        return None, None, "features_outside_training_scope"
    x = [(value-mean)/scale for value, mean, scale in zip(features, norm["mean"], norm["scale"])]
    logits = [sum(a*b for a, b in zip(row, x))+bias for row, bias in zip(model["weights"], model["bias"])]
    if any(not math.isfinite(v) for v in logits):
        return None, None, "invalid_model_output"
    pivot = max(logits)
    exp = [math.exp(value-pivot) for value in logits]
    total = sum(exp)
    scores = [value/total for value in exp]
    ordered = sorted(range(4), key=lambda i: scores[i], reverse=True)
    best, runner_up = ordered[:2]
    if scores[best] < 0.60 or scores[best]-scores[runner_up] < 0.15:
        return None, None, "ambiguous_model_pattern"
    return CLASSES[best], scores[best], None


def infer_devices(devices, model_path=None):
    """Return learned patterns with abstention, never physical fault diagnoses."""
    result = {
        "status": "unavailable", "model": None,
        "inputs_sha256": _input_hash(devices) if isinstance(devices, list) else None,
        "devices": [], "limitations": list(LIMITATIONS),
    }
    if not isinstance(devices, list) or not devices:
        result["status"] = "insufficient"
        return result
    if len(devices) > 100 or result["inputs_sha256"] is None:
        return result
    try:
        model, sha = _load_model(DEFAULT_MODEL if model_path is None else model_path)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError):
        return result
    result["model"] = {"id": MODEL_ID, "sha256": sha, "training_data": "synthetic", "algorithm": "multinomial_logistic_regression"}
    seen = set()
    for device in devices:
        identifier = device.get("id") if isinstance(device, dict) else None
        output = {"id": identifier if isinstance(identifier, str) else None,
                  "status": "unavailable", "pattern": None, "score": None,
                  "signals": [], "reason_codes": [], "ambiguities": []}
        result["devices"].append(output)
        if not isinstance(identifier, str) or not identifier or len(identifier) > 120 or identifier in seen:
            output["reason_codes"] = ["invalid_or_duplicate_device_id"]
            continue
        seen.add(identifier)
        try:
            features, signals = extract_features(device)
            output["signals"] = signals
            pattern, score, reason = _predict(features, model)
            if reason:
                output["status"] = "insufficient"
                output["reason_codes"] = [reason]
                continue
            # Missingness never becomes an affirmative normal/reading result.
            if features[8] > 0 and pattern != "dropout":
                output["status"] = "insufficient"
                output["reason_codes"] = ["missing_data_model_disagreement"]
                continue
            if (pattern == "stuck" and features[4]*23 < 6) or (pattern == "dropout" and features[8] == 0):
                output["status"] = "insufficient"
                output["reason_codes"] = ["pattern_evidence_disagreement"]
                continue
            output.update(status="ready", pattern=pattern, score=score)
            ambiguity = {
                "persistent_shift": "soil_change_or_sensor_shift_indistinguishable",
                "stuck": "stable_environment_or_stuck_sensor_indistinguishable",
                "dropout": "missing_telemetry_cause_unknown",
            }.get(pattern)
            if ambiguity:
                output["ambiguities"] = [ambiguity]
        except InputError as exc:
            output["status"] = exc.status
            output["reason_codes"] = [exc.code]
        except (ValueError, TypeError, OverflowError, ZeroDivisionError):
            output["reason_codes"] = ["invalid_input"]
    states = [d["status"] for d in result["devices"]]
    result["status"] = "ready" if "ready" in states else ("insufficient" if "insufficient" in states else "unavailable")
    return result
