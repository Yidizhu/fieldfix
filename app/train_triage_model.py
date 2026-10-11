"""Offline synthetic training only; runtime inference has no NumPy dependency."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import random

from triage_model import (
    CLASSES, FEATURE_ORDER, MODEL_ID, extract_features, infer_devices,
    parameters_sha256, _predict,
)

TRAIN_SEED = 20261011
VALIDATION_SEED = 20261012
CONTROL_SEED = 20261013
TRAIN_PER_CLASS = 800
VALIDATION_PER_CLASS = 250


def synthetic_device(rng, pattern, identifier="generated"):
    """Generate independent traces; no product case imports or private data."""
    level = rng.uniform(18, 76)
    amplitude = rng.uniform(0.3, 2.5)
    phase = rng.uniform(-math.pi, math.pi)
    noise = rng.uniform(0.025, 0.50)
    drift = rng.uniform(-0.012, 0.012)
    values = [level + amplitude*math.sin(2*math.pi*i/24+phase) + drift*i + rng.gauss(0, noise)
              for i in range(72)]
    if pattern == "normal":
        small_shift = rng.uniform(-0.6, 0.6)
        for i in range(48, 72):
            values[i] += small_shift + 0.35*math.sin((i-48)/rng.uniform(7, 14))
    elif pattern == "persistent_shift":
        shift = rng.choice([-1, 1])*rng.uniform(5, 14)
        onset = rng.choice([48, 48, 49, 50, 51, 52])
        for i in range(onset, 72):
            values[i] += shift
    elif pattern == "stuck":
        onset = rng.randint(48, 57)
        fixed = values[onset-1] + rng.uniform(-2, 2)
        for i in range(onset, 72):
            values[i] = fixed
    elif pattern == "dropout":
        onset = rng.randint(48, 66)
        for i in range(onset, 72):
            values[i] = None
    else:
        raise ValueError("unknown_synthetic_pattern")
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return {"id": identifier, "points": [
        {"t": (start+timedelta(hours=i)).isoformat().replace("+00:00", "Z"), "value": value}
        for i, value in enumerate(values)
    ]}


def _dataset(seed, per_class):
    rng = random.Random(seed)
    features, labels, devices = [], [], []
    for label, pattern in enumerate(CLASSES):
        for i in range(per_class):
            device = synthetic_device(rng, pattern, f"generated-{label}-{i}")
            x, _ = extract_features(device)
            features.append(x)
            labels.append(label)
            devices.append(device)
    return features, labels, devices


def _metrics(devices, labels, model_path):
    matrix = {truth: {label: 0 for label in CLASSES+["abstain"]} for truth in CLASSES}
    for offset in range(0, len(devices), 100):
        output = infer_devices(devices[offset:offset+100], model_path)
        for item, truth in zip(output["devices"], labels[offset:offset+100]):
            predicted = item["pattern"] if item["status"] == "ready" else "abstain"
            matrix[CLASSES[truth]][predicted] += 1
    total = sum(sum(row.values()) for row in matrix.values())
    correct = sum(matrix[label][label] for label in CLASSES)
    abstained = sum(row["abstain"] for row in matrix.values())
    accepted = total-abstained
    return {
        "examples": total, "accepted": accepted, "abstained": abstained,
        "coverage": accepted/total,
        "correct_fraction_of_all_examples": correct/total,
        "accuracy_among_accepted_synthetic_examples": correct/accepted if accepted else None,
        "confusion_matrix_including_abstentions": matrix,
    }


def _controls(model_path):
    rng = random.Random(CONTROL_SEED)
    groups = {}
    for kind in ("different_levels", "unseen_slow_drydown", "unseen_rain_pulse", "high_noise", "quantized_normal", "physical_step_confounded"):
        rows = []
        for i in range(80):
            device = synthetic_device(rng, "normal", f"{kind}-{i}")
            points = device["points"]
            if kind == "different_levels":
                target = (5, 20, 50, 80, 94)[i % 5]
                offset = target-sum(p["value"] for p in points[:48])/48
                for p in points:
                    p["value"] += offset
            elif kind == "unseen_slow_drydown":
                for j in range(48, 72):
                    points[j]["value"] -= (j-48)*rng.uniform(0.04, 0.12)
            elif kind == "unseen_rain_pulse":
                peak = rng.uniform(3, 8)
                width = rng.uniform(2, 5)
                for j in range(48, 72):
                    points[j]["value"] += peak*math.exp(-0.5*((j-55)/width)**2)
            elif kind == "high_noise":
                for p in points:
                    p["value"] += rng.gauss(0, 4)
            elif kind == "quantized_normal":
                for p in points:
                    p["value"] = round(p["value"], 1)
            elif kind == "physical_step_confounded":
                # These exact readings could be an irrigation event OR offset.
                # A label cannot determine which physical cause produced them.
                for p in points[48:]:
                    p["value"] += 9
            rows.append(device)
        result = infer_devices(rows, model_path)
        counts = {name: 0 for name in CLASSES+["abstain"]}
        ambiguous = 0
        for item in result["devices"]:
            counts[item["pattern"] if item["status"] == "ready" else "abstain"] += 1
            ambiguous += bool(item["ambiguities"])
        groups[kind] = {"examples": len(rows), "outcomes": counts, "explicit_cause_ambiguity_count": ambiguous}
    return groups


def train(output, card_json, card_txt):
    import numpy as np
    x_raw, labels, _ = _dataset(TRAIN_SEED, TRAIN_PER_CLASS)
    x_raw = np.asarray(x_raw, dtype=np.float64)
    y = np.asarray(labels, dtype=np.int64)
    mean, scale = x_raw.mean(axis=0), x_raw.std(axis=0)
    scale = np.maximum(scale, 1e-6)
    x = (x_raw-mean)/scale
    w, b = np.zeros((len(FEATURE_ORDER), 4)), np.zeros(4)
    target = np.eye(4)[y]
    initial_loss = math.log(4)
    learning_rate, regularization, steps = 0.08, 0.002, 1600
    for _ in range(steps):
        logits = x @ w+b
        logits -= logits.max(axis=1, keepdims=True)
        probability = np.exp(logits)
        probability /= probability.sum(axis=1, keepdims=True)
        gradient = (probability-target)/len(x)
        w -= learning_rate*(x.T @ gradient+regularization*w)
        b -= learning_rate*gradient.sum(axis=0)
    logits = x @ w+b
    logits -= logits.max(axis=1, keepdims=True)
    probability = np.exp(logits)
    probability /= probability.sum(axis=1, keepdims=True)
    final_loss = float(-np.log(probability[np.arange(len(y)), y]).mean())
    # Bounds are fitted on training features only, with an explicit margin.
    lower, upper = x_raw.min(axis=0), x_raw.max(axis=0)
    span = np.maximum(upper-lower, 0.01)
    lower = np.maximum(0, lower-0.25*span)
    upper += 0.25*span
    rounded = lambda values: np.round(values, 12).tolist()
    model = {
        "id": MODEL_ID, "version": 1, "algorithm": "multinomial_logistic_regression",
        "training_data": "synthetic", "training_seed": TRAIN_SEED,
        "validation_seed": VALIDATION_SEED, "negative_control_seed": CONTROL_SEED,
        "split": "Independently generated traces, disjoint RNG seeds; no product-case inputs; normalization and support bounds fit on training only.",
        "feature_order": FEATURE_ORDER, "classes": CLASSES,
        "normalization": {"mean": rounded(mean), "scale": rounded(scale), "lower": rounded(lower), "upper": rounded(upper)},
        "weights": rounded(w.T), "bias": rounded(b),
        "abstention": {"minimum_score": 0.60, "minimum_margin": 0.15},
        "training": {"examples": len(labels), "examples_per_class": TRAIN_PER_CLASS,
                     "optimizer": "full_batch_gradient_descent", "steps": steps,
                     "learning_rate": learning_rate, "l2": regularization,
                     "initial_cross_entropy": initial_loss, "final_cross_entropy": final_loss},
        "input_contract": {"points": 72, "history_points": 48, "evaluation_points": 24,
                           "cadence_seconds": 3600, "value_unit": "VWC percentage points", "value_range": [0, 100]},
        "purpose": "Classify learned temporal patterns; cannot identify physical hardware causes or authorize payments.",
    }
    model["parameters_sha256"] = parameters_sha256(model)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(model, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    _, held_labels, held_devices = _dataset(VALIDATION_SEED, VALIDATION_PER_CLASS)
    evaluation = _metrics(held_devices, held_labels, output)
    controls = _controls(output)
    sha = hashlib.sha256(output.read_bytes()).hexdigest()
    card = {
        "id": MODEL_ID, "model_sha256": sha, "parameters_sha256": model["parameters_sha256"],
        "training": model["training"], "seeds": {"training": TRAIN_SEED, "validation": VALIDATION_SEED, "negative_controls": CONTROL_SEED},
        "environment": {"numpy": np.__version__}, "evaluation": evaluation, "negative_controls": controls,
        "feature_order": FEATURE_ORDER, "split": model["split"],
        "limitations": [
            "All training and evaluation labels describe self-generated patterns, not verified faults.",
            "Synthetic held-out performance cannot estimate field performance, accuracy or warranty eligibility.",
            "A genuine irrigation step and an additive sensor offset can yield identical readings; the model cannot separate their causes.",
            "Flat readings can represent a stable environment or a stuck sensor; cause remains ambiguous.",
            "Missing telemetry does not locate a gateway or hardware failure.",
            "Only complete hourly 48+24 windows in VWC percentage points are supported; there is no live field validation.",
            "Abstention checks are engineering guards around learned linear decision surfaces, not trained cause diagnosis.",
        ],
        "provenance": {"private_research_used": False, "product_cases_used_in_training": False,
                       "cloud_api_used": False, "numpy_used_only_for_offline_training": True,
                       "runtime_inference_standard_library_only": True, "pickle_used": False},
    }
    card_json.parent.mkdir(parents=True, exist_ok=True)
    card_json.write_text(json.dumps(card, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    description = """FieldFix triage pattern model v1
================================
This is a trained multiclass logistic regression, not a named scenario lookup.
Offline full-batch gradient descent learns a 12-feature by 4-class weight matrix
and four biases from 3,200 independently generated synthetic traces. Runtime
computes those features, standardizes them using training-only statistics and
applies the learned frozen weights and softmax. NumPy is training-only; runtime
uses the Python standard library and a versioned JSON artifact, never pickle.

Input: 72 timezone-aware, ordered hourly observations per device; first 48
historical, last 24 evaluated; values 0–100 VWC percentage points or explicit
missing slots. IDs only identify records. Names, gateway metadata, labels,
scenario hints and UI case IDs are not classifier features. Input SHA-256 binds
only device IDs and the supplied t/value observations. Model SHA-256 hashes the
actual file bytes; parameters_sha256 covers feature order, class order,
normalization and learned weights/bias. JSON has no timestamp so retraining with
the same environment/seed produces a reproducible artifact.

Normal, persistent_shift, stuck and dropout describe observation patterns.
Scores are softmax model scores, not calibrated confidence, field accuracy or
hardware-failure probabilities. A real irrigation step and sensor offset can be
observationally identical; every persistent_shift output explicitly retains
that ambiguity. A stable environment and stuck sensor are likewise inseparable
without independent evidence. Topology is not used to identify any cause.

Missing values are never imputed. Historical missingness or intermittent/short
evaluation gaps abstain. A contiguous missing tail of at least 6 hourly slots
can be classified by the learned dropout class; a conflicting predicted class
is rejected. A stuck prediction without at least six hours of exactly flat
readings, or a dropout prediction with no missing readings, is also rejected.
Timing errors, invalid/nonfinite values, unsupported ranges and
excessive historical noise reject input. Low model score/margin or feature
values outside training support abstain. Constant or near-constant history is
insufficient. These are explicit engineering guards, not learned fault causes.

All splits use independent random seeds. Means, scales and feature support are
fit on training only. The held-out set has 1,000 synthetic examples. Separate
negative controls cover different levels, new drydown/rain-pulse shapes,
quantization, high noise and physically confounded irrigation steps. See JSON
for actual counts, coverage, accepted-example accuracy and abstentions, including
unfavorable outcomes. Those counts are synthetic checks, not field performance.

No private research, model checkpoint, cloud service, customer data, live sensor
or product-case training input is used. No purchase or payment authority exists.
The pre-existing research LSTM remains a separate historical inference artifact.
"""
    card_txt.write_text(description+"\nActual model SHA-256: "+sha+"\n\nHeld-out synthetic evaluation:\n"+json.dumps(evaluation, indent=2)+"\n\nNegative controls:\n"+json.dumps(controls, indent=2)+"\n", encoding="utf-8")
    return {"model_sha256": sha, "training_initial_loss": initial_loss, "training_final_loss": final_loss,
            "evaluation": evaluation, "negative_controls": controls}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    base = Path(__file__).resolve().parent
    parser.add_argument("--output", type=Path, default=base/"models/triage-model-v1.json")
    args = parser.parse_args()
    docs = base.parent/"docs"
    report = train(args.output, docs/"triage-model-card-v1.json", docs/"triage-model-card-v1.txt")
    print(json.dumps(report, ensure_ascii=True))


if __name__ == "__main__":
    main()
