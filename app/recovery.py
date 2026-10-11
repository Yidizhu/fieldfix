"""Deterministic recovery evidence for a synthetic FieldFix demonstration.

This module does not load research data, call a diagnostic model, authorize a
purchase, or certify hardware. Scenario names select immutable fixture inputs;
the evaluator only reads numeric observations, timestamps, and link states.
The reference is an independently specified synthetic trace, not ground truth
from a field instrument. All thresholds are explicit demo choices, not fitted
or validated operating limits for real farms.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from statistics import fmean
from typing import Any


EXPECTED_SAMPLES = 24
INTERVAL_MINUTES = 60
MIN_PAIRED_SAMPLES = 18
MIN_LINK_SAMPLES = 22
MIN_LINK_SUCCESS_RATIO = 0.90
MIN_REFERENCE_RANGE = 1.0
MAX_MEAN_ABSOLUTE_ERROR = 1.5
MAX_ABSOLUTE_ERROR = 3.0
MIN_SENSOR_RANGE = 0.05
METRIC_DECIMAL_PLACES = 4

# Deliberately varies enough to expose a stuck sensor; this reference is not
# derived from the sensor under evaluation or from the requested result label.
_REFERENCE = (
    30.0, 30.4, 30.9, 31.6, 32.4, 33.3, 34.1, 34.8,
    35.2, 35.0, 34.6, 34.0, 33.4, 32.8, 32.3, 31.9,
    31.6, 31.7, 32.1, 32.6, 33.2, 33.9, 34.5, 35.1,
)
_OFFSETS = (0.10, -0.20, 0.15, -0.10, 0.25, -0.15)
_START = datetime(2026, 10, 8, tzinfo=timezone.utc)

_EXPLANATIONS = {
    "pass": (
        "The synthetic post-service observations meet all fixed demo checks. "
        "This is a demonstration result, not validated real-world evidence or "
        "a hardware repair certification."
    ),
    "fail": (
        "At least one evaluable check fails on the synthetic post-service "
        "observations. Recovery is not demonstrated; review the failed checks. "
        "This does not establish the cause of a real hardware fault."
    ),
    "insufficient": (
        "The synthetic post-service observations do not provide enough "
        "usable coverage or reference variation to assess recovery. "
        "Missing evidence must not be treated as a successful repair."
    ),
}


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        result = float(value)
    except OverflowError:
        return None
    return result if math.isfinite(result) else None


def _span(values: list[float]) -> float | None:
    return max(values) - min(values) if values else None


def _display_number(value: float | None) -> float | None:
    return round(value, METRIC_DECIMAL_PLACES) if value is not None and math.isfinite(value) else None


def _fixture_observations(scenario: str) -> list[dict[str, Any]]:
    observations = []
    for index, reference in enumerate(_REFERENCE):
        sensor = round(reference + _OFFSETS[index % len(_OFFSETS)], 2)
        link_up: bool | None = True
        if scenario == "still_faulty":
            sensor = 30.8  # Still connected, but stuck while reference changes.
        elif scenario == "insufficient" and index >= 6:
            sensor, reference, link_up = None, None, None
        observations.append({
            "t": (_START + timedelta(minutes=index * INTERVAL_MINUTES))
            .isoformat().replace("+00:00", "Z"),
            "sensor": sensor,
            "reference": reference,
            "link_up": link_up,
        })
    return observations


def _evaluate_observations(raw_observations: list[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate evidence without scenario labels; kept separate for controls.

    A failed, adequately supported check takes precedence over incomplete
    unrelated checks. Thus a fully observed link outage can fail even when it
    leaves no online numeric pairs. Numeric checks never judge a short sample.
    """
    observations = []
    times: list[datetime | None] = []
    for raw in raw_observations:
        raw = raw if isinstance(raw, dict) else {}
        raw_time = raw.get("t")
        when = None
        if isinstance(raw_time, str):
            try:
                parsed = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
                if parsed.tzinfo is not None:
                    when = parsed.astimezone(timezone.utc)
            except (ValueError, OverflowError):
                pass
        times.append(when)
        raw_link = raw.get("link_up")
        link = raw_link if type(raw_link) is bool else None
        observations.append({
            "t": when.isoformat().replace("+00:00", "Z") if when else None,
            "sensor": _number(raw.get("sensor")),
            "reference": _number(raw.get("reference")),
            "link_up": link,
        })

    window_valid = (
        len(times) == EXPECTED_SAMPLES
        and all(when is not None for when in times)
        and all((current - previous).total_seconds() == INTERVAL_MINUTES * 60
                for previous, current in zip(times, times[1:]))
    )
    pairs = [
        (item["sensor"], item["reference"])
        for item in observations
        if item["link_up"] is True
        and item["sensor"] is not None and item["reference"] is not None
        and math.isfinite(item["sensor"] - item["reference"])
    ]
    pair_count = len(pairs)
    online_count = sum(item["link_up"] is True for item in observations)
    offline_count = sum(item["link_up"] is False for item in observations)
    known_links = online_count + offline_count
    link_ratio = online_count / known_links if known_links else None
    residuals = [abs(sensor - reference) for sensor, reference in pairs]
    # Scaling before summing avoids overflow from otherwise finite inputs.
    mean_error = None
    if residuals:
        scale = max(residuals)
        mean_error = scale * fmean(error / scale for error in residuals) if scale else 0.0
    # Evaluate the same declared four-decimal precision that the report shows,
    # so floating-point representation cannot flip a displayed boundary value.
    mean_error = _display_number(mean_error)
    max_error = _display_number(max(residuals) if residuals else None)
    sensor_range = _display_number(_span([sensor for sensor, _ in pairs]))
    reference_range = _display_number(_span([reference for _, reference in pairs]))
    pairs_ready = window_valid and pair_count >= MIN_PAIRED_SAMPLES
    links_ready = window_valid and known_links >= MIN_LINK_SAMPLES
    reference_ready = pairs_ready and reference_range is not None and reference_range >= MIN_REFERENCE_RANGE

    def check(code: str, value: Any, operator: str, threshold: Any,
              unit: str, ready: bool, passed: bool, failure: str = "fail") -> dict[str, Any]:
        return {"code": code, "status": ("pass" if passed else failure) if ready else "insufficient",
                "value": value, "operator": operator, "threshold": threshold, "unit": unit}

    checks = [
        check("observation_window", window_valid, "eq", True, "hourly_window", True,
              window_valid, "insufficient"),
        check("paired_samples", pair_count, "gte", MIN_PAIRED_SAMPLES, "samples",
              window_valid, pairs_ready, "insufficient"),
        check("link_samples", known_links, "gte", MIN_LINK_SAMPLES, "samples",
              window_valid, links_ready, "insufficient"),
        check("link_success_ratio", _display_number(link_ratio), "gte", MIN_LINK_SUCCESS_RATIO,
              "ratio", links_ready, link_ratio is not None and link_ratio >= MIN_LINK_SUCCESS_RATIO),
        check("reference_variation", _display_number(reference_range), "gte", MIN_REFERENCE_RANGE,
              "percentage_points", pairs_ready,
              reference_range is not None and reference_range >= MIN_REFERENCE_RANGE, "insufficient"),
        check("mean_absolute_error", _display_number(mean_error), "lte", MAX_MEAN_ABSOLUTE_ERROR,
              "percentage_points", reference_ready and mean_error is not None,
              mean_error is not None and mean_error <= MAX_MEAN_ABSOLUTE_ERROR),
        check("max_absolute_error", _display_number(max_error), "lte", MAX_ABSOLUTE_ERROR,
              "percentage_points", reference_ready and max_error is not None,
              max_error is not None and max_error <= MAX_ABSOLUTE_ERROR),
        check("sensor_variation", _display_number(sensor_range), "gt", MIN_SENSOR_RANGE,
              "percentage_points", reference_ready and sensor_range is not None,
              sensor_range is not None and sensor_range > MIN_SENSOR_RANGE),
    ]
    statuses = {item["status"] for item in checks}
    status = "fail" if "fail" in statuses else "insufficient" if "insufficient" in statuses else "pass"
    return {
        "status": status,
        "sample_count": pair_count,
        "metrics": {
            "method": "fixed_synthetic_recovery_rules_v1",
            "measurement_unit": "percent",
            "residual_unit": "percentage_points",
            "metric_decimal_places": METRIC_DECIMAL_PLACES,
            "expected_sample_count": EXPECTED_SAMPLES,
            "observation_count": len(observations),
            "interval_minutes": INTERVAL_MINUTES,
            "valid_pair_count": pair_count,
            "missing_pair_count": len(observations) - pair_count,
            "link_known_count": known_links,
            "link_online_count": online_count,
            "link_offline_count": offline_count,
            "link_unknown_count": len(observations) - known_links,
            "link_success_ratio": _display_number(link_ratio),
            "mean_absolute_error": _display_number(mean_error),
            "max_absolute_error": _display_number(max_error),
            "sensor_range": _display_number(sensor_range),
            "reference_range": _display_number(reference_range),
            "thresholds": {
                "min_paired_samples": MIN_PAIRED_SAMPLES,
                "min_link_samples": MIN_LINK_SAMPLES,
                "min_link_success_ratio": MIN_LINK_SUCCESS_RATIO,
                "min_reference_range": MIN_REFERENCE_RANGE,
                "max_mean_absolute_error": MAX_MEAN_ABSOLUTE_ERROR,
                "max_absolute_error": MAX_ABSOLUTE_ERROR,
                "min_sensor_range_exclusive": MIN_SENSOR_RANGE,
            },
        },
        "checks": checks,
        "observations": observations,
        "explanation": _EXPLANATIONS[status],
    }


def evaluate_recovery(scenario: str) -> dict[str, Any]:
    """Return fresh, JSON-safe recovery evidence for one synthetic scenario.

    Supported selectors: ``recovered``, ``still_faulty``, ``insufficient``.
    ``sample_count`` counts finite sensor/reference pairs with an online link.
    Invalid selectors raise ValueError; no case, payment, or database changes.
    """
    if not isinstance(scenario, str) or scenario not in {"recovered", "still_faulty", "insufficient"}:
        raise ValueError("Unknown recovery scenario; use recovered, still_faulty, or insufficient.")
    evidence = _evaluate_observations(_fixture_observations(scenario))
    return {"scenario": scenario, "source": "synthetic_fixture", **evidence}
