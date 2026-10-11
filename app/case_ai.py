"""Bind learned pattern evidence to service cases without deciding repair or payment.

The learned classifier consumes observations only. Shared connectivity is a
separate, explicit topology check. Both are investigation leads, not fault truth.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from analysis_engine import analyze
from triage_model import infer_devices

TEXT = {
    "shared_dropout": ("AI 发现多支设备停止上传，共享连接值得先检查。", "AI found several devices stopped reporting. Check their shared connection first."),
    "persistent_shift": ("AI 发现持续读数偏移，需要结合现场情况复核。", "AI found a persistent reading shift that needs a field-context review."),
    "stuck": ("AI 发现读数长时间不变，需要核对现场变化和设备。", "AI found readings stayed flat. Check field conditions and the device."),
    "normal": ("AI 暂未发现所学范围内的异常模式。", "AI found no unusual pattern within its learned scope."),
    "single_dropout": ("AI 发现上传中断，恢复数据后再判断读数。", "AI found a reporting gap. Restore data before assessing readings."),
    "insufficient": ("部分观测不足或不适用，AI 暂不能给出完整判断。", "Some observations are insufficient or outside scope. AI cannot complete the assessment."),
    "unavailable": ("AI 分析暂不可用，请恢复分析后再批准付费处理。", "AI analysis is unavailable. Restore it before approving paid work."),
    "disagreement": ("AI 与独立规则的结果不一致，需要补充检查。", "AI and the independent checks disagree. More investigation is needed."),
}
METHOD = ("案件 AI 使用合成序列训练的多类逻辑回归，实际读取本案观测运行推断；"
          "独立统计规则检查输入和共享连接。模式提示不能区分真实土壤变化与设备问题，"
          "也不批准维修或付款。")
METHOD_EN = ("Case AI runs a multiclass logistic-regression model trained on synthetic sequences against this case's observations. "
             "Independent statistical checks assess data and shared connectivity. Pattern flags do not distinguish real soil changes "
             "from device issues and do not approve repairs or payments.")


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def attach_case_ai(case, model_path=None):
    result = deepcopy(case)
    series = result.get("series", [])
    baseline = analyze(series)
    learned = infer_devices(series, model_path=model_path)
    devices = learned.get("devices", [])
    status = learned.get("status", "unavailable")
    if status not in ("ready", "insufficient", "unavailable"):
        status = "unavailable"
    if status == "ready" and (len(devices) != len(series) or not devices or any(d.get("status") != "ready" for d in devices)):
        status = "insufficient"
    if status != "ready":
        code = status
    else:
        shifts = [d for d in devices if d["pattern"] == "persistent_shift"]
        flat = [d for d in devices if d["pattern"] == "stuck"]
        gaps = [d for d in devices if d["pattern"] == "dropout"]
        # Shared causes are a transparent context rule, never a model diagnosis.
        if gaps and baseline["category"] == "shared_connection" and set(baseline["affected_devices"]).issubset({d["id"] for d in gaps}):
            code = "shared_dropout"
        elif gaps:
            code = "single_dropout"
        elif shifts:
            code = "persistent_shift"
        elif flat:
            code = "stuck"
        elif all(d["pattern"] == "normal" for d in devices) and baseline["category"] == "normal":
            code = "normal"
        else:
            code = "disagreement"
            status = "insufficient"
    category = {"shared_dropout":"shared_connection", "persistent_shift":"reading_anomaly", "stuck":"reading_anomaly", "normal":"normal"}.get(code, "insufficient_data")
    wanted = {"shared_dropout":"dropout", "single_dropout":"dropout", "persistent_shift":"persistent_shift", "stuck":"stuck"}.get(code)
    highlighted = [d for d in devices if d.get("pattern") == wanted] if wanted else []
    signal_codes = {"shared_dropout":("trailing_missing_hours",), "single_dropout":("trailing_missing_hours",),
                    "persistent_shift":("median_residual_vwc", "detection_observed_points"), "stuck":("flat_duration_hours", "historical_noise_vwc")}.get(code, ())
    signals = []
    for device in highlighted[:3]:
        for signal in device.get("signals", []):
            if signal.get("code") in signal_codes:
                signals.append(dict(deepcopy(signal), device_id=device["id"]))
    ai = deepcopy(learned)
    ai.update({"status":status, "summary_code":code, "pattern":wanted or ("normal" if code=="normal" else None),
               "model_executed":any(d.get("score") is not None for d in devices), "signals":signals,
               "context_sha256":digest([{k: d.get(k) for k in ("id", "gateway_id")} for d in series]),
               "rule_context":{"category":baseline["category"], "affected_devices":baseline["affected_devices"]},
               "decision_authority":"human_only"})
    ai["evidence_sha256"] = digest(ai)
    ai["generated_at"] = datetime.now(timezone.utc).isoformat()
    result["ai"] = ai
    result["baseline_analysis"] = baseline
    analysis = deepcopy(baseline)
    analysis.update(category=category, severity="low" if category=="normal" else "medium", summary=TEXT[code][0], method=METHOD)
    if category == "shared_connection":analysis["severity"] = "high"
    analysis["affected_devices"] = [d["id"] for d in highlighted] if highlighted else ([] if category=="normal" else [d.get("id") for d in devices if d.get("status")!="ready"])
    if category == "reading_anomaly":
        analysis["next_steps"] = ["先核对降雨、灌溉和近期安装或维护记录。", "检查探头接触与连接；必要时使用独立测量作对照。", "记录技术员结论后，再决定观察、维修、保修或替换。"]
    elif category == "insufficient_data":
        analysis["next_steps"] = ["补充逐小时观测与真实设备连接关系。", "对缺数设备先检查上传和供电情况。"]
    result["analysis"] = analysis
    return result
