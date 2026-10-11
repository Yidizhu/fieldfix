"""Explainable FieldFix demonstration analysis; every bundled observation is synthetic.

No trained research model or hardware diagnosis is claimed here. The first 48
hourly observations calibrate each device independently; later observations are
held out for detection. Missing observations are not interpolated. The analysis
never authorizes purchases and never uses scenario labels as evidence.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any

CALIBRATION_POINTS = 48
MIN_CALIBRATION_VALUES = 36
MIN_DETECTION_VALUES = 6
METHOD = (
    "演示规则与时间序列基线：按设备独立使用前48个小时点校准小时基线，"
    "后续点只用于检测；连续6个有效点同向偏离才提示读数异常。"
    "仅将已知共享采集器、缺数开始时间相近的设备关联；不读取场景标签。"
    "结果是排查线索，不是硬件损坏结论。"
)


def _result(category: str, severity: str, summary: str, evidence: list[str],
            next_steps: list[str], affected: list[str]) -> dict[str, Any]:
    return {"category": category, "severity": severity, "summary": summary,
            "evidence": evidence, "next_steps": next_steps,
            "affected_devices": affected, "method": METHOD}


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        return None
    return float(value) if math.isfinite(value) else None


def _points(device: dict[str, Any]) -> list[tuple[datetime, float | None]]:
    """Normalize timestamps and invalid values; do not fill missing readings."""
    by_time: dict[datetime, float | None] = {}
    raw_points = device.get("points", [])
    if not isinstance(raw_points, list):
        return []
    for point in raw_points:
        if not isinstance(point, dict) or not isinstance(point.get("t"), str):
            continue
        try:
            when = datetime.fromisoformat(point["t"].replace("Z", "+00:00"))
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            when = when.astimezone(timezone.utc)
        except (ValueError, OverflowError):
            continue
        by_time[when] = _number(point.get("value"))
    return sorted(by_time.items())


def _device_details(device: dict[str, Any], index: int) -> dict[str, Any]:
    points = _points(device)
    identifier = str(device.get("id") or f"device-{index + 1}")
    name = str(device.get("name") or identifier)
    gateway = device.get("gateway_id")
    gateway = str(gateway).strip() if gateway is not None else ""
    if gateway.lower() in {"unknown", "none", "null", "未知"}:
        gateway = ""
    details: dict[str, Any] = {
        "id": identifier, "name": name, "gateway": gateway,
        "points": points, "stale_start": None, "missing_count": 0,
        "anomalous": False, "usable": False,
    }
    if not points:
        return details
    trailing = 0
    for _, value in reversed(points):
        if value is not None:
            break
        trailing += 1
    details["missing_count"] = trailing
    if trailing >= 3 and trailing < len(points):
        details["stale_start"] = points[len(points) - trailing][0]
    if len(points) <= CALIBRATION_POINTS:
        return details
    calibration = points[:CALIBRATION_POINTS]
    detection = points[CALIBRATION_POINTS:]
    # This demo accepts hourly samples only: a long hidden gap must not turn
    # six scattered readings into a spurious six-hour persistent anomaly.
    intervals = [(b[0] - a[0]).total_seconds() for a, b in zip(points, points[1:])]
    if any(abs(interval - 3600) > 1 for interval in intervals):
        details["timing_issue"] = True
        return details
    if sum(value is not None for _, value in calibration) < MIN_CALIBRATION_VALUES:
        return details
    buckets: dict[int, list[float]] = {}
    for when, value in calibration:
        if value is not None:
            buckets.setdefault(when.hour, []).append(value)
    baseline = {hour: median(values) for hour, values in buckets.items()}
    calibration_residuals = [value - baseline[when.hour] for when, value in calibration
                             if value is not None and when.hour in baseline]
    centre = median(calibration_residuals)
    mad = median(abs(value - centre) for value in calibration_residuals)
    # Values represent volumetric soil moisture in percentage points. This
    # floor is an illustrative demo setting, not an agronomic threshold.
    threshold = max(4.0, 6.0 * 1.4826 * mad)
    residuals = [(when, None if value is None or when.hour not in baseline
                  else value - baseline[when.hour]) for when, value in detection]
    valid_residuals = [value for _, value in residuals if value is not None]
    if len(valid_residuals) < MIN_DETECTION_VALUES:
        return details
    details["usable"] = True
    details["threshold"] = threshold
    details["calibration_count"] = sum(value is not None for _, value in calibration)
    details["detection_count"] = len(valid_residuals)
    run = 0
    previous_sign = 0
    maximum_run = 0
    for _, residual in residuals:
        if residual is None or abs(residual) <= threshold:
            run = 0
            previous_sign = 0
            continue
        sign = 1 if residual > 0 else -1
        run = run + 1 if sign == previous_sign else 1
        previous_sign = sign
        maximum_run = max(maximum_run, run)
    details["max_run"] = maximum_run
    details["median_residual"] = median(valid_residuals)
    details["anomalous"] = maximum_run >= MIN_DETECTION_VALUES
    return details


def analyze(devices: list[dict[str, Any]]) -> dict[str, Any]:
    """Return evidence from measurements/topology, never a purchase decision.

    Accepted input fields are id, name, gateway_id, points, and optionally
    battery/last_seen_minutes/expected_upload_minutes for callers' displays.
    Timing evidence comes from the actual hourly point history. Optional status
    summaries and unknown fields cannot override that evidence.
    """
    if not isinstance(devices, list) or not devices:
        return _result("insufficient_data", "low", "没有可供分析的设备观测。",
                       ["未收到有效设备列表。"], ["先导入带时间戳的观测和设备连接关系。"], [])
    details = [_device_details(device, i) for i, device in enumerate(devices)
               if isinstance(device, dict)]
    if not details:
        return _result("insufficient_data", "low", "没有有效的设备观测。",
                       ["设备输入格式不完整。"], ["检查设备列表与时间戳字段。"], [])
    # Known shared topology and synchronized missing points provide an
    # association. They do not establish the cause of missing telemetry.
    offline = [item for item in details if item["stale_start"] is not None]
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in offline:
        if item["gateway"]:
            groups.setdefault(item["gateway"], []).append(item)
    for gateway, group in sorted(groups.items()):
        if len(group) < 2:
            continue
        starts = [item["stale_start"] for item in group]
        if (max(starts) - min(starts)).total_seconds() > 3600:
            continue
        names = "、".join(item["name"] for item in group)
        evidence = [
            f"{len(group)}支设备关联到同一已知采集器 {gateway}：{names}。",
            f"缺失读数从 {min(starts).strftime('%Y-%m-%d %H:%M UTC')} 附近开始，开始时间相差不超过1小时。",
            f"这些设备末尾分别连续缺少 {'、'.join(str(item['missing_count']) for item in group)} 个小时点；没有对缺失数据插值。",
            "共同缺数与公共链路问题相容，但不能据此确认采集器故障，也不能认定所有探头损坏。",
        ]
        return _result("shared_connection", "high", "多支设备同步缺数，优先检查共享连接。", evidence,
                       ["核查采集器供电、网络与最近维护记录。", "现场检查公共链路后，观察各通道是否恢复。",
                        "尚无证据支持逐支换新；恢复上传后再评估读数。"],
                       [item["id"] for item in group])
    anomalous = [item for item in details if item["anomalous"]]
    if anomalous:
        evidence = [
            f"{item['name']}：前{item['calibration_count']}个有效历史点用于校准，后续{item['detection_count']}个有效点用于检测；"
            f"最长连续{item['max_run']}小时同向超出±{item['threshold']:.1f}个百分点的演示阈值。"
            for item in anomalous]
        evidence += ["异常判定使用每支设备自身的历史小时基线，没有把不同土壤水平直接互相比高低。",
                     "持续偏差可能来自真实土壤变化、安装接触、设备问题或基线失配；当前证据不能确认硬件损坏。"]
        if offline:
            evidence.append("另外存在末段缺数的设备，相关连接仍需单独核查。")
        return _result("reading_anomaly", "medium", "发现持续读数偏差，需要结合现场信息复核。", evidence,
                       ["先核对降雨、灌溉和近期安装或维护记录。", "检查探头接触与连接；必要时使用独立测量作对照。",
                        "记录技术员结论后，再决定观察、维修、保修或替换。"],
                       [item["id"] for item in anomalous])
    insufficient = [item for item in details if not item["usable"] or item["missing_count"] >= 3]
    if insufficient:
        evidence = []
        for item in insufficient:
            if item.get("timing_issue"):
                evidence.append(f"{item['name']}：时间间隔不符合本演示的逐小时输入要求。")
            elif item["missing_count"] >= 3:
                evidence.append(f"{item['name']}：末尾连续缺少{item['missing_count']}个小时点。")
            else:
                evidence.append(f"{item['name']}：历史校准或后续检测数据不足。")
        if any(not item["gateway"] for item in offline):
            evidence.append("部分设备的采集器关系未知；不能把同时缺数直接归因于同一个采集器。")
        evidence.append("不能把缺失观测解释成正常，也不能直接解释为硬件损坏。")
        return _result("insufficient_data", "medium", "现有数据不足以完成读数判断。", evidence,
                       ["补充逐小时观测与真实设备连接关系。", "对缺数设备先检查上传和供电情况。"],
                       [item["id"] for item in insufficient])
    return _result("normal", "low", "本次演示规则未发现持续异常。",
                   [f"已分别检查{len(details)}支设备；校准窗口与检测窗口分开。",
                    "没有检测到连续6小时同向超过各自历史基线阈值的读数。",
                    "未触发规则不等于设备完全健康；缓慢变化或其他类型故障可能未被本方法覆盖。"],
                   ["继续观察并保留灌溉、天气及维护记录。", "如有现场异常，仍应独立检查。"], [])


def _series(identifier: str, name: str, gateway: str, level: float,
            offset: float = 0.0, missing_from: int | None = None) -> dict[str, Any]:
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    points = []
    for hour in range(72):
        # Reproducible illustrative hourly moisture pattern. There is no
        # research dataset, external measurement, or hidden diagnosis label.
        value = level + 0.8 * math.sin(2 * math.pi * (hour % 24) / 24)
        value += 0.08 * math.cos(hour * 1.7)
        if hour >= CALIBRATION_POINTS:
            value += offset + 0.3 * math.sin((hour - CALIBRATION_POINTS) / 8)
        points.append({"t": (start + timedelta(hours=hour)).isoformat().replace("+00:00", "Z"),
                       "value": None if missing_from is not None and hour >= missing_from else round(value, 3)})
    missing = 0 if missing_from is None else 72 - missing_from
    return {"id": identifier, "name": name, "gateway_id": gateway, "points": points,
            "battery": 82, "expected_upload_minutes": 60,
            "last_seen_minutes": (missing + 1) * 60 if missing else 0}


def get_cases() -> list[dict[str, Any]]:
    """Return three fresh, fully synthetic cases with analysis recomputed."""
    definitions = [
        ("FF-101", "三个通道同时缺少数据", "演示农场 · 北区", "GW-NORTH", (None, None, None), 60),
        ("FF-102", "单支探头持续偏离历史模式", "演示农场 · 东区", "GW-EAST", (0.0, 9.0, 0.0), None),
        ("FF-103", "不同土壤水平下的正常变化", "演示农场 · 南区", "GW-SOUTH", (0.0, 0.0, 0.0), None),
    ]
    cases = []
    for case_id, title, site, gateway, offsets, missing_from in definitions:
        series = [_series(f"{case_id}-S{i + 1}", f"探头 {i + 1}", gateway, level,
                          offset=offsets[i] or 0.0, missing_from=missing_from)
                  for i, level in enumerate((22.0, 35.0, 49.0))]
        cases.append({"id": case_id, "title": title, "site": site,
                      "device_names": [device["name"] for device in series],
                      "gateway_id": gateway, "series": series, "analysis": analyze(series),
                      "provenance": "synthetic"})
    return cases

