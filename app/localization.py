"""Response-only localization. Original evidence and user-authored notes stay intact.

Translations use a closed catalogue of system sentences and anchored parameter
patterns. Unknown text is never machine-translated or guessed. Domain objects,
readings, identifiers, decisions, money and persisted history are not mutated.
"""
from copy import deepcopy
import re
from locale_extra import (SYSTEM as EXTRA_SYSTEM, METHODS, ERRORS, HISTORY, PREFIXES, PATTERNS, MISC, RECOVERY)

DEFAULT_LOCALE = "zh-CN"


def normalize_locale(value=None, default=DEFAULT_LOCALE):
    value = str(value or "").strip().lower().replace("_", "-")
    for code in ("en", "es", "fr", "pt"):
        if value == code or value.startswith(code + "-"):
            return code
    if value == "zh" or value.startswith("zh-"):
        return "zh-CN"
    return default


SYSTEM_TEXT = {
    "三个通道同时缺少数据": "Three channels stopped reporting together",
    "单支探头持续偏离历史模式": "One probe persistently differs from its historical pattern",
    "不同土壤水平下的正常变化": "Normal variation across different soil moisture levels",
    "演示农场 · 北区": "Demo farm · North field",
    "演示农场 · 东区": "Demo farm · East field",
    "演示农场 · 南区": "Demo farm · South field",
    "没有可供分析的设备观测。": "No device observations are available for analysis.",
    "未收到有效设备列表。": "No valid device list was received.",
    "先导入带时间戳的观测和设备连接关系。": "Import timestamped observations and device connection information first.",
    "没有有效的设备观测。": "No valid device observations are available.",
    "设备输入格式不完整。": "The device input format is incomplete.",
    "检查设备列表与时间戳字段。": "Check the device list and timestamp fields.",
    "共同缺数与公共链路问题相容，但不能据此确认采集器故障，也不能认定所有探头损坏。": "The shared data gap is consistent with a common connection issue. It does not confirm a gateway failure or show that all probes are damaged.",
    "多支设备同步缺数，优先检查共享连接。": "Several devices have synchronized data gaps. Check the shared connection first.",
    "核查采集器供电、网络与最近维护记录。": "Check gateway power, network connectivity and recent maintenance records.",
    "现场检查公共链路后，观察各通道是否恢复。": "Inspect the shared connection on site, then check whether each channel resumes reporting.",
    "尚无证据支持逐支换新；恢复上传后再评估读数。": "The evidence does not support replacing each probe. Reassess readings after reporting resumes.",
    "异常判定使用每支设备自身的历史小时基线，没有把不同土壤水平直接互相比高低。": "Each device is compared with its own historical hourly baseline, rather than with different soil moisture levels at other devices.",
    "持续偏差可能来自真实土壤变化、安装接触、设备问题或基线失配；当前证据不能确认硬件损坏。": "A persistent difference may reflect real soil changes, installation contact, a device issue or a poorly matched baseline. Current evidence does not confirm hardware damage.",
    "另外存在末段缺数的设备，相关连接仍需单独核查。": "Other devices also have recent data gaps; check their connections separately.",
    "发现持续读数偏差，需要结合现场信息复核。": "A persistent reading difference needs review alongside on-site information.",
    "先核对降雨、灌溉和近期安装或维护记录。": "First review rainfall, irrigation and recent installation or maintenance records.",
    "检查探头接触与连接；必要时使用独立测量作对照。": "Inspect probe contact and connections; use an independent measurement for comparison if needed.",
    "记录技术员结论后，再决定观察、维修、保修或替换。": "Record the technician's findings before choosing observation, repair, a warranty request or replacement.",
    "部分设备的采集器关系未知；不能把同时缺数直接归因于同一个采集器。": "Some gateway relationships are unknown. Simultaneous data gaps cannot be attributed to one shared gateway.",
    "不能把缺失观测解释成正常，也不能直接解释为硬件损坏。": "Missing observations establish neither normal operation nor hardware damage.",
    "现有数据不足以完成读数判断。": "There is not enough data to assess the readings.",
    "补充逐小时观测与真实设备连接关系。": "Add hourly observations and verified device connection information.",
    "对缺数设备先检查上传和供电情况。": "For devices with data gaps, first check reporting and power.",
    "本次演示规则未发现持续异常。": "The demo rules did not find a persistent anomaly.",
    "没有检测到连续6小时同向超过各自历史基线阈值的读数。": "No readings exceeded their own baseline threshold in the same direction for 6 consecutive hours.",
    "未触发规则不等于设备完全健康；缓慢变化或其他类型故障可能未被本方法覆盖。": "No alert does not prove device health. This method may miss gradual changes or other fault types.",
    "继续观察并保留灌溉、天气及维护记录。": "Continue observation and keep irrigation, weather and maintenance records.",
    "如有现场异常，仍应独立检查。": "Independently investigate any unusual on-site observations.",
    "演示规则与时间序列基线：按设备独立使用前48个小时点校准小时基线，后续点只用于检测；连续6个有效点同向偏离才提示读数异常。仅将已知共享采集器、缺数开始时间相近的设备关联；不读取场景标签。结果是排查线索，不是硬件损坏结论。": "Demo rules and a time-series baseline: each device's first 48 hourly points calibrate its hourly baseline; later points are detection-only. A reading alert needs 6 consecutive valid points deviating in the same direction. Devices are grouped only when they share a known gateway and their data gaps start at similar times. Scenario labels are not used. Results are investigation clues, not a hardware-damage diagnosis.",
}

from case_ai import TEXT as AI_TEXT, METHOD as AI_METHOD, METHOD_EN as AI_METHOD_EN
SYSTEM_TEXT.update({zh: en for zh, en in AI_TEXT.values()})
SYSTEM_TEXT[AI_METHOD] = AI_METHOD_EN
SYSTEM_EXTRA = dict(EXTRA_SYSTEM)
SYSTEM_EXTRA[AI_METHOD] = METHODS["ai"]
SYSTEM_EXTRA[next(key for key in SYSTEM_TEXT if key.startswith("演示规则与时间序列基线："))] = METHODS["baseline"]

ERROR_TEXT = {
    "AI 证据尚未就绪，不能进入替换、保修或新交易；请先补齐证据。": "AI evidence is not ready. Complete the evidence before replacement, warranty or a new transaction.",
    "AI 证据标识不完整，不能进入替换、保修或新交易。": "AI evidence identifiers are incomplete. Replacement, warranty and new transactions are blocked.",
    "当前人工复核没有绑定可用 AI 证据；请重新复核后再批准新交易。": "This review is not bound to usable AI evidence. Review it again before approving a new transaction.",
    "AI 模型或案件证据已变化；请重新进行人工复核后再批准新交易。": "The AI model or case evidence changed. Repeat human review before approving a new transaction.",
    "仅允许本地访问。": "Only local access is allowed.",
    "未找到页面。": "Page not found.",
    "请刷新本地页面后再操作。": "Refresh the local page before trying this action again.",
    "不允许跨站操作。": "Cross-site requests are not allowed.",
    "请求格式必须为 JSON。": "The request must use JSON.",
    "操作不存在。": "This action does not exist.",
    "请求长度无效。": "The request length is invalid.",
    "请求内容无效。": "The request content is invalid.",
    "处理未完成。请检查服务日志或稍后重试。": "The action could not be completed. Check the service logs or try again later.",
    "案件不存在。": "Case not found.",
    "已有交易记录，不能覆盖前序复核。": "A transaction record already exists; the earlier review cannot be overwritten.",
    "请填写 8–1000 字的检查记录。": "Enter an inspection note containing 8–1000 characters.",
    "请选择有效处理方式。": "Choose a valid handling option.",
    "当前证据不支持进入单支更换或保修流程。": "Current evidence does not support a single-probe replacement or warranty workflow.",
    "需要明确确认这是演练中的人工检查记录。": "Explicitly confirm that this is a human inspection record for the demonstration.",
    "先记录人工检查并选择过保替换。": "First record a human inspection and select out-of-warranty replacement.",
    "采购需要明确批准。": "Purchasing requires explicit approval.",
    "未通过人工复核与采购批准，不能执行交易。": "A transaction requires both human review and purchasing approval.",
    "已有 Sandbox 订单，不能改成本地演练。": "A Sandbox order already exists and cannot be changed to a local rehearsal.",
    "本案已有本地演练记录。使用另一份测试数据库运行 Sandbox。": "This case already has a local rehearsal record. Use a separate test database for Sandbox transactions.",
    "没有可核验的 Sandbox 订单。": "There is no Sandbox order available to verify.",
    "先完成案件复核。": "Complete the case review first.",
    "采购流程尚未完成。": "The purchasing workflow is not complete.",
    "保修为申请草稿，尚未接入商家处理与验收。": "The warranty request is a draft; merchant processing and acceptance are not connected.",
    "请确认模拟复查并填写 8–1000 字观察记录。": "Confirm the simulated follow-up and enter an observation note containing 8–1000 characters.",
    "PayPal Sandbox 未完成请求。请检查配置或稍后重试；不要另建重复订单。": "PayPal Sandbox did not complete the request. Check the configuration or try again later; do not create duplicate orders.",
    "尚未配置 PayPal Sandbox 测试凭据。": "PayPal Sandbox test credentials have not been configured.",
    "Sandbox 授权失败。": "Sandbox authentication failed.",
    "Sandbox 未返回有效的测试付款链接。": "Sandbox did not return a valid test payment link.",
    "订单编号无效。": "The order ID is invalid.",
    "买家尚未完成批准，订单未捕获。": "Buyer approval is not complete. The order has not been captured.",
    "订单编号不一致，需要人工复核。": "The order ID does not match and requires human review.",
    "订单明细数量不符合预期。": "The number of purchase units does not match the expected order.",
    "订单与案件不一致，需要人工复核。": "The order does not match the case and requires human review.",
    "订单金额或币种不符合预期。": "The order amount or currency does not match the expected quote.",
    "付款状态尚未完成。": "Payment is not yet complete.",
    "付款记录数量不符合预期。": "The number of payment records is not as expected.",
    "付款金额、币种或状态不符合预期。": "The payment amount, currency or status does not match the expected values.",
}

ERROR_TEXT.update({'未通过人工复核与报价批准，不能执行交易。': 'A transaction requires human review and quote approval.', '原请求已超过安全重试期限；请核对交易或人工处理，不能新建重复订单。': 'The original request is outside the safe retry window. Reconcile it or seek manual review; do not create a duplicate order.', '旧版交易记录仅供查阅，请使用新演示案件。': 'Previous-version transactions are read-only. Use a fresh demonstration case.', '上一笔请求结果尚未确定；请重试同一操作或核对原交易。': 'The earlier request is unresolved. Retry the same operation or reconcile the existing transaction.', '报价需要明确批准。': 'The quote requires explicit approval.', '本地演练与 Sandbox 交易不能混用，请使用独立测试案件。': 'Local rehearsals and Sandbox transactions cannot be mixed. Use separate test cases.', '没有可核验的授权订单。': 'There is no authorization order to verify.', '扣款需要再次明确确认金额与恢复复核结果。': 'Charging requires another explicit confirmation of the amount and reviewed recovery evidence.', '恢复证据尚未通过检查和人工复核，禁止扣款。': 'Recovery evidence has not passed the checks and human review. Charging is blocked.', '当前授权不可扣款。': 'This authorization cannot be charged.', '撤销授权需要明确确认。': 'Voiding an authorization requires explicit confirmation.', '当前授权不可撤销；请先核对是否已扣款。': 'This authorization cannot be voided. Check whether it has already been charged.', '本地演练没有可查询的 PayPal 交易。': 'A local rehearsal has no PayPal transaction to query.', '缺少已核验的授权编号。': 'A verified authorization ID is missing.', '请先完成授权；已结算或撤销的记录不可修改恢复证据。': 'Complete authorization first. Recovery evidence cannot change after settlement or a void.', '请选择有效的模拟恢复数据场景。': 'Choose a valid synthetic recovery scenario.', '恢复证据尚未通过检查，不能确认恢复。': 'Recovery evidence has not passed the checks; recovery cannot be accepted.', '旧版直接扣款订单不可用于先授权后扣款流程。': 'A previous direct-capture order cannot be used in the authorization-first workflow.', '买家尚未批准此授权订单；尚未扣款。': 'The buyer has not approved this authorization order. No charge has been made.', '订单授权记录不完整，需要人工核查。': 'The order authorization record is incomplete and needs human review.', '授权编号与本案不一致，需要人工核查。': 'The authorization ID does not match this case and needs human review.', '授权金额或币种不符合预期。': 'The authorization amount or currency does not match the approved quote.', '授权状态不适用于本演示，需要人工核查。': 'This authorization status is unsupported by the demo and needs human review.', '授权有效期不完整，需要人工核查。': 'Authorization validity information is incomplete and needs human review.', '授权尚不可扣款；请先核对交易状态。': 'This authorization is not ready to charge. Reconcile its status first.', '授权已超过本演示的三天扣款期限；请人工处理，不能自动重新授权。': 'The authorization is beyond this demo’s three-day charge window. Manual handling is required; it cannot be reauthorized automatically.', '未取得可核查的扣款编号；请保持本案并核对原交易。': 'No verifiable capture ID was returned. Keep this case and reconcile the original transaction.', '尚未核实授权撤销；请核对原交易，不要新建订单。': 'The authorization void is not verified. Reconcile the original transaction; do not create a new order.', '扣款记录不属于本案授权。': 'The capture does not belong to this case’s authorization.'})

HISTORY_TEXT = {
    "批准模拟目录 FF-Soil-01，NZD 25.00；演示政策设为过保，兼容性为模拟声明。": "Approved simulated catalogue item FF-Soil-01, NZD 25.00. The demo policy treats it as out of warranty; compatibility is a simulated claim.",
    "本地交易演练已记录；未调用 PayPal，未产生付款。": "Local transaction rehearsal recorded. PayPal was not called and no payment occurred.",
    "Sandbox 测试订单已创建，等待买家批准。": "Sandbox test order created; waiting for buyer approval.",
    "服务端核验 Sandbox 捕获已完成；设备仍待安装与复查。": "The server verified a completed Sandbox capture. Device installation and follow-up inspection are still pending.",
}
HISTORY_TEXT.update({'Sandbox 请求已开始；结果未核实前禁止执行相反操作。': 'A Sandbox request has started. Conflicting operations are blocked until its result is verified.', '已批准模拟服务报价 NZD 25.00；监测服务商为卖方，农场为买方。': 'Approved the simulated NZD 25.00 service quote. The monitoring service provider is the seller and the farm is the buyer.', '本地授权演练已记录；未调用 PayPal，未冻结或扣取任何款项。': 'Local authorization rehearsal recorded. PayPal was not called; no funds were held or charged.', 'Sandbox 授权订单已创建，等待测试买家批准；尚未扣款。': 'Sandbox authorization order created, awaiting the test buyer’s approval. No charge yet.', '已重新查询 Sandbox 原交易；付款状态与维修状态分别保留。': 'The existing Sandbox transaction was queried again. Payment and repair states remain separate.', '本地扣款演练已记录；未调用 PayPal，未发生真实或 Sandbox 付款。': 'Local capture rehearsal recorded. PayPal was not called; no real or Sandbox payment occurred.', '本地撤销授权演练已记录；未调用 PayPal。': 'Local authorization void rehearsed. PayPal was not called.', 'Sandbox 授权已核验；款项暂时保留，尚未扣取。': 'Sandbox authorization verified. Funds are held temporarily and have not been charged.', 'Sandbox 扣款已核验；这不代表真实设备已修复。': 'Sandbox capture verified. This does not establish that real hardware has been repaired.', 'Sandbox 授权已撤销；未执行扣款。': 'Sandbox authorization voided. No charge was made.', 'Sandbox 仍在处理，尚不能确认扣款或授权完成。': 'Sandbox is still processing. Authorization or capture completion is not confirmed.', 'Sandbox 授权已过期，禁止继续扣款。': 'Sandbox authorization expired. Further charging is blocked.', 'Sandbox 拒绝本次交易，未记录为成功。': 'Sandbox denied this transaction; it is not recorded as successful.', 'Sandbox 状态已更新。': 'Sandbox status updated.', '已检查模拟恢复数据；更换证据后需要重新进行人工复核。': 'Synthetic recovery evidence checked. Changing the evidence requires a new human review.'})

HISTORY_PREFIXES = {
    "模拟恢复证据已由人复核，非真实维修：": "Synthetic recovery evidence reviewed by a human; not a real repair: ",
    "人工复核已记录（模拟现场检查）：": "Human review recorded (simulated on-site inspection): ",
    "模拟复查已记录，非真实维修：": "Simulated follow-up recorded; this was not a real repair: ",
}


def _name(value, names):
    return names.get(value, value)


# Full-string patterns are the exact sentences emitted by analysis_engine.
# All captures (device names, counts, timestamps and thresholds) are preserved.
ANALYSIS_PATTERNS = [
    (re.compile(r"(?P<count>\d+)支设备关联到同一已知采集器 (?P<gateway>.+?)：(?P<names>.+)。"),
     lambda m, names: f"{m['count']} devices share the known gateway {m['gateway']}: "
                     + ", ".join(_name(name, names) for name in m['names'].split('、')) + "."),
    (re.compile(r"缺失读数从 (?P<start>.+?) 附近开始，开始时间相差不超过(?P<hours>\d+)小时。"),
     lambda m, names: f"Data gaps start around {m['start']}, within {m['hours']} hour of one another."),
    (re.compile(r"这些设备末尾分别连续缺少 (?P<counts>[\d、]+) 个小时点；没有对缺失数据插值。"),
     lambda m, names: "These devices respectively lack " + m['counts'].replace('、', ', ')
                     + " consecutive hourly points at the end. Missing data was not interpolated."),
    (re.compile(r"(?P<name>.+)：前(?P<calibration>\d+)个有效历史点用于校准，后续(?P<detection>\d+)个有效点用于检测；最长连续(?P<run>\d+)小时同向超出±(?P<threshold>[\d.]+)个百分点的演示阈值。"),
     lambda m, names: f"{_name(m['name'], names)}: {m['calibration']} valid historical points were used for calibration and "
                     f"{m['detection']} subsequent valid points for detection. The longest same-direction exceedance of the "
                     f"±{m['threshold']} percentage-point demo threshold lasted {m['run']} consecutive hours."),
    (re.compile(r"(?P<name>.+)：时间间隔不符合本演示的逐小时输入要求。"),
     lambda m, names: f"{_name(m['name'], names)}: sampling intervals do not meet this demo's hourly input requirement."),
    (re.compile(r"(?P<name>.+)：末尾连续缺少(?P<count>\d+)个小时点。"),
     lambda m, names: f"{_name(m['name'], names)}: the last {m['count']} consecutive hourly points are missing."),
    (re.compile(r"(?P<name>.+)：历史校准或后续检测数据不足。"),
     lambda m, names: f"{_name(m['name'], names)}: historical calibration or subsequent detection data is insufficient."),
    (re.compile(r"已分别检查(?P<count>\d+)支设备；校准窗口与检测窗口分开。"),
     lambda m, names: f"Checked {m['count']} devices separately, using distinct calibration and detection windows."),
]


def translate_analysis_text(text, names=None, locale="en"):
    if not isinstance(text, str):
        return text
    locale = normalize_locale(locale)
    if locale == "zh-CN":
        return text
    if text in SYSTEM_TEXT:
        return SYSTEM_TEXT[text] if locale == "en" else SYSTEM_EXTRA[text][locale]
    for index, (pattern, render) in enumerate(ANALYSIS_PATTERNS):
        match = pattern.fullmatch(text)
        if match:
            if locale == "en":
                return render(match, names or {})
            values = match.groupdict()
            if "name" in values:
                values["name"] = _name(values["name"], names or {})
            if "names" in values:
                values["names"] = ", ".join(_name(name, names or {}) for name in values["names"].split("、"))
            if "counts" in values:
                values["counts"] = values["counts"].replace("、", ", ")
            return PATTERNS[str(index)][locale].format_map(values)
    prefix = "Original evidence (translation unavailable): " if locale == "en" else MISC["original_evidence"][locale]
    return prefix + text


def localize_analysis(analysis, locale=DEFAULT_LOCALE, names=None):
    result = deepcopy(analysis)
    locale = normalize_locale(locale)
    if locale == "zh-CN":
        return result
    for key in ("summary", "method"):
        if key in result:
            result[key] = translate_analysis_text(result[key], names, locale)
    for key in ("evidence", "next_steps"):
        if key in result:
            result[key] = [translate_analysis_text(value, names, locale) for value in result[key]]
    return result


RECOVERY_ZH = {'The synthetic post-service observations meet all fixed demo checks. This is a demonstration result, not validated real-world evidence or a hardware repair certification.': '合成维修后观测满足全部固定演示检查。这是演示结果，不是经过验证的真实现场证据，也不是硬件维修认证。', 'At least one evaluable check fails on the synthetic post-service observations. Recovery is not demonstrated; review the failed checks. This does not establish the cause of a real hardware fault.': '合成维修后观测至少有一项可评估检查未通过。尚未证明恢复，请复核失败项；这不能确定真实硬件故障的原因。', 'The synthetic post-service observations do not provide enough usable coverage or reference variation to assess recovery. Missing evidence must not be treated as a successful repair.': '合成维修后观测缺少足够有效覆盖或参考变化，无法评估恢复。证据缺失不能视为维修成功。'}

def localize_workflow(state, locale=DEFAULT_LOCALE):
    result = deepcopy(state)
    locale = normalize_locale(locale)
    recovery = result.get("recovery")
    if isinstance(recovery, dict):
        original = recovery.get("explanation", "")
        if locale == "zh-CN":
            display = RECOVERY_ZH.get(original, original)
        elif locale == "en" or original not in RECOVERY_ZH:
            display = original
        else:
            code = dict(zip(RECOVERY_ZH, ("pass", "fail", "insufficient")))[original]
            display = RECOVERY[code][locale]
        recovery["display_explanation"] = display
    for event in result.get("history", []):
        text = event.get("text", "")
        display = text
        if locale != "zh-CN":
            if text in HISTORY_TEXT:
                display = HISTORY_TEXT[text] if locale == "en" else HISTORY[text][locale]
            else:
                for prefix, translated in HISTORY_PREFIXES.items():
                    if text.startswith(prefix):
                        translated = translated if locale == "en" else PREFIXES[prefix][locale].rstrip() + " "
                        display = translated + text[len(prefix):]
                        break
                else:
                    prefix = "Recorded event (original text): " if locale == "en" else MISC["original_event"][locale]
                    display = prefix + text
        event["display_text"] = display
    return result


def localize_case(case, locale=DEFAULT_LOCALE):
    result = deepcopy(case)
    locale = normalize_locale(locale)
    names = {}
    if locale != "zh-CN" and result.get("provenance") == "synthetic":
        for device in result.get("series", []):
            name = device.get("name", "")
            match = re.fullmatch(r"探头 (\d+)", name)
            if match:
                names[name] = ("Probe " if locale == "en" else MISC["probe"][locale]) + match[1]
                device["name"] = names[name]
        result["device_names"] = [_name(name, names) for name in result.get("device_names", [])]
        for key in ("title", "site"):
            if key in result and result[key] in SYSTEM_TEXT:
                result[key] = SYSTEM_TEXT[result[key]] if locale == "en" else SYSTEM_EXTRA[result[key]][locale]
    if "analysis" in result:
        result["analysis"] = localize_analysis(result["analysis"], locale, names)
    if "workflow" in result:
        result["workflow"] = localize_workflow(result["workflow"], locale)
    return result


def localize_error(text, locale=DEFAULT_LOCALE):
    locale = normalize_locale(locale)
    if locale == "zh-CN":
        return text
    if locale == "en":
        return ERROR_TEXT.get(text, "This action could not be completed. Review the request or try again later.")
    return ERRORS.get(text, MISC["error"])[locale]


def localize_response(payload, locale=DEFAULT_LOCALE):
    """Translate a copy at the HTTP boundary, without changing persisted data."""
    locale = normalize_locale(locale)
    result = deepcopy(payload)
    if "cases" in result:
        result["cases"] = [localize_case(case, locale) for case in result["cases"]]
    if "history" in result:
        result = localize_workflow(result, locale)
    if "error" in result:
        result["error"] = localize_error(result["error"], locale)
    result["locale"] = locale
    return result
