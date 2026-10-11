"""Read-only, allowlisted projection of locally imported research results.

This module never calls a model, changes a workflow, or performs a payment.
The private input lives outside static assets and is not a public demo dataset.
"""
from __future__ import annotations

from datetime import date, timedelta
import json
import math
from pathlib import Path
import re

MODE = "precomputed_research_replay"
LIMITATIONS = ["daily_not_realtime", "replay_not_live_inference",
               "injected_not_hardware_truth", "no_payment_link",
               "local_only_unpublished", "threshold_not_field_validated",
               "retrospective_test_threshold", "clean_not_ground_truth"]


class ResearchError(ValueError):
    pass


def _text(value, limit=160):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ResearchError("Invalid research metadata")
    if any(c in value for c in ("/", "\\", "\x00", "\n", "\r")):
        raise ResearchError("Paths are not public research metadata")
    return value


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ResearchError("Invalid research number")
    return value


def project_dataset(raw):
    """Recompute alarms from scores and a frozen threshold; ignore supplied flags."""
    if not isinstance(raw, dict):
        raise ResearchError("Invalid research dataset")
    threshold = _number(raw.get("threshold"))
    if raw.get("cadence") != "daily" or raw.get("threshold_rule") != "score > threshold":
        raise ResearchError("Unsupported research rule")
    if raw.get("provenance") not in ("research_output_with_injected_faults", "synthetic_contract_fixture"):
        raise ResearchError("Unknown provenance")
    points = raw.get("points")
    if not isinstance(points, list) or not 1 <= len(points) <= 730:
        raise ResearchError("Invalid research window")
    by_date = {}
    previous = None
    for point in points:
        if not isinstance(point, dict):
            raise ResearchError("Invalid research point")
        t = point.get("t")
        if not isinstance(t, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", t):
            raise ResearchError("Daily dates required")
        current = date.fromisoformat(t)
        if previous is not None and current <= previous:
            raise ResearchError("Duplicate or unordered research dates")
        previous = current
        score = point.get("score")
        if score is not None:
            score = _number(score)
        by_date[current] = {"t": t, "score": score,
                            "alarm": None if score is None else score > threshold}
    first, last = min(by_date), max(by_date)
    days = (last - first).days + 1
    if days > 730:
        raise ResearchError("Research window too long")
    dense = []
    for i in range(days):
        when = first + timedelta(days=i)
        dense.append(by_date.get(when, {"t": when.isoformat(), "score": None, "alarm": None}))
    valid = sum(p["score"] is not None for p in dense)
    alarms = sum(p["alarm"] is True for p in dense)
    sources = raw.get("sources")
    if not isinstance(sources, list) or not 1 <= len(sources) <= 4:
        raise ResearchError("Research sources required")
    clean_sources = []
    for source in sources:
        digest = source.get("sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ResearchError("Source digest required")
        clean_sources.append({"name": _text(source.get("name")), "sha256": digest,
                              "role": _text(source.get("role"), 100)})
    result = {key: _text(raw.get(key)) for key in ("id", "title", "model", "score_name", "threshold_source", "scenario_code")}
    result.update(cadence="daily", provenance=raw["provenance"], threshold=threshold,
                  threshold_rule="score > threshold", sources=clean_sources,
                  window={"start": first.isoformat(), "end": last.isoformat()},
                  metrics={"points": days, "valid_points": valid, "missing_points": days-valid,
                           "alarm_points": alarms, "alarm_fraction": alarms / valid if valid else None},
                  points=dense, limitations=list(LIMITATIONS))
    return result


def read_research(path: Path | None):
    empty = {"schema_version": "1.0", "mode": MODE, "datasets": []}
    if path is None or not path.is_file():
        return dict(empty, status="unconfigured")
    try:
        if path.stat().st_size > 2_000_000:
            raise ResearchError("Research projection too large")
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("schema_version") != "1.0" or raw.get("mode") != MODE:
            raise ResearchError("Unknown research format")
        datasets = raw.get("datasets")
        if not isinstance(datasets, list) or not 1 <= len(datasets) <= 6:
            raise ResearchError("Invalid research selection")
        projected = [project_dataset(d) for d in datasets]
        if len({d["id"] for d in projected}) != len(projected):
            raise ResearchError("Duplicate research identifiers")
        return dict(empty, status="ready", datasets=projected)
    except (ValueError, TypeError, KeyError, AttributeError, OSError, OverflowError):
        # Never leak absolute paths or private source contents through errors.
        return dict(empty, status="invalid")
