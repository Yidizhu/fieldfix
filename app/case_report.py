"""Safe, read-only, printable case reports. No network or filesystem access."""
from __future__ import annotations
import base64
import hashlib
from html import escape
import re
from localization import localize_case, normalize_locale
from locale_extra import REPORT as REPORT_EXTRA

REPORT_CSS = """@page{size:A4;margin:16mm}*{box-sizing:border-box}body{font-family:Arial,'Microsoft YaHei',sans-serif;color:#172d44;line-height:1.55;font-size:13px;margin:28px auto;padding:0 24px;max-width:980px}h1{font-size:26px;margin:0 0 8px}h2{font-size:19px;margin:26px 0 10px;border-bottom:1px solid #ccd6df;padding-bottom:7px}h3{font-size:15px;margin:18px 0 8px}p{margin:8px 0;overflow-wrap:anywhere}.notice{padding:12px 14px;background:#f1f5f8;border-left:3px solid #406585}.muted{color:#526a7e;font-size:12px}table{width:100%;border-collapse:collapse;margin:10px 0 18px;table-layout:fixed}th,td{border:1px solid #d8e0e7;padding:8px 10px;text-align:left;vertical-align:top;overflow-wrap:anywhere}th{background:#f4f7fa;font-weight:600}table.pairs th{width:31%}.note{white-space:pre-wrap}.version{border-top:2px solid #9aafbd;margin-top:24px;padding-top:3px}code{font-size:11px;overflow-wrap:anywhere;white-space:normal}header,footer{margin:0 0 18px}footer{border-top:1px solid #ccd6df;margin-top:28px;padding-top:12px;font-size:12px;color:#526a7e}@media(max-width:560px){body{padding:0 14px;margin:20px auto;font-size:12px}h1{font-size:22px}th,td{padding:7px 6px}table.pairs th{width:37%}}@media print{body{max-width:none;margin:0;padding:0;font-size:10pt}h1{font-size:19pt}h2,h3{break-after:avoid}tr{break-inside:avoid}thead{display:table-header-group}details.ai-details>*{display:block}details.ai-details>summary{font-weight:600}.notice{background:transparent}a{color:inherit;text-decoration:none}}"""
REPORT_STYLE_CSP = "'sha256-" + base64.b64encode(hashlib.sha256(REPORT_CSS.encode('utf-8')).digest()).decode('ascii') + "'"
REPORT_CSP = "default-src 'none'; style-src " + REPORT_STYLE_CSP + "; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"

# Every generated label is translated. Human-authored notes retain their language.
TEXT = {
 'title': ('Case outcome summary', '案件处理摘要'),
 'case': ('Case', '案件'), 'case_title': ('Case title', '案件标题'),
 'synthetic': ('All case observations and field checks are synthetic or simulated.', '案件观测及现场检查均为合成或模拟。'),
 'unknown_data': ('Data provenance is not recorded. No real-world validation is claimed.', '数据来源属性未记录；不声明已通过真实场景验证。'),
 'baseline': ('Case analysis uses a demonstration statistical baseline. It is an inspection lead, not a validated hardware diagnosis or live research-model inference.', '案件分析使用演示统计基线，提供排查线索；不属于已验证硬件诊断，也不是研究模型实时推断。'),
 'separate': ('Payment does not prove repair. Recovery evidence, human acceptance and transaction status are reported separately.', '付款不证明设备已修好。恢复证据、人工验收和交易状态分别记录。'),
 'permission': ('This report does not grant permission to publish research data, model files or private source material.', '本报告不构成研究数据、模型文件或私有来源材料的公开发布许可。'),
 'redaction': ('Notes retain their original language. Local paths and sensitive values are omitted from this report; original stored records are unchanged.', '备注保留原语言；报告隐去本机路径和敏感值，原始存储记录未被改写。'),
 'missing': ('Not recorded', '未记录'), 'unknown': ('Unknown', '未知'),
 'yes': ('Recorded', '已记录'), 'no': ('Not recorded', '未记录'),
 'overview': ('Current outcome', '当前处理结果'), 'analysis': ('Initial evidence', '初始证据'),
 'category': ('Analysis category', '分析类别'), 'summary': ('Evidence summary', '证据摘要'),
 'method': ('Analysis method', '分析方法'), 'decision': ('Human decision', '人工决定'),
 'note': ('Original inspection note', '原文检查备注'),
 'approved': ('Quote approval', '报价批准'), 'quote': ('Approved quote', '已批准报价'),
 'quote_version': ('Quote version', '报价版本'), 'item': ('Service / item', '服务或项目'),
 'amount': ('Amount', '金额'), 'currency': ('Currency', '币种'),
 'seller': ('Seller role', '卖方角色'), 'buyer': ('Buyer role', '买方角色'),
 'quote_at': ('Approval time', '报价批准时间'),
 'monitoring_service_provider': ('Monitoring service provider', '监测服务商'), 'farm': ('Farm', '农场'),
 'payment': ('Transaction state', '交易状态'), 'mode': ('Transaction mode', '交易模式'),
 'intent': ('Order intent', '订单类型'), 'order_id': ('Order ID', '订单编号'),
 'authorization_id': ('Authorization ID', '授权编号'), 'capture_id': ('Capture ID', '扣款编号'),
 'record_id': ('Local rehearsal ID', '本地演练编号'), 'pending': ('Unresolved request', '待核请求'),
 'pending_action': ('Operation', '操作'), 'started_at': ('Request started', '请求开始时间'),
 'local_rehearsal': ('Local rehearsal — no PayPal call or funds movement', '本地演练——未调用 PayPal，未移动资金'),
 'paypal_sandbox': ('PayPal Sandbox — virtual test funds only', 'PayPal Sandbox——仅虚拟测试资金'),
 'awaiting_buyer': ('Awaiting buyer approval; not charged', '等待买家批准；未扣款'),
 'authorized': ('Authorized; not charged', '已授权；未扣款'),
 'completed': ('Charge recorded', '已记录扣款'), 'voided': ('Authorization voided; not charged', '授权已撤销；未扣款'),
 'payment_pending': ('Provider result unresolved', '提供方结果尚未核实'),
 'expired': ('Authorization expired', '授权已过期'), 'denied': ('Transaction denied', '交易被拒绝'),
 'legacy_payment': ('Legacy payment record; not evidence of the current repair-before-charge workflow.', '旧版交易记录，不证明已走过当前先验收再扣款流程。'),
 'recovery': ('Recovery evidence', '恢复证据'), 'source': ('Evidence source', '证据来源'),
 'scenario': ('Evidence scenario', '证据场景'), 'samples': ('Valid paired samples', '有效配对样本数'),
 'pass': ('Demo checks passed', '演示检查通过'), 'fail': ('Demo checks failed', '演示检查未通过'),
 'insufficient': ('Insufficient evidence', '证据不足'),
 'acceptance': ('Human acceptance', '人工验收'), 'repair': ('Repair / follow-up state', '维修或复查状态'),
 'unverified': ('Not accepted / unverified', '未验收或未验证'),
 'verified_demo': ('Simulated acceptance recorded; no real repair certification', '已记录模拟验收；不是真实维修认证'),
 'acceptance_note': ('Original acceptance note', '原文验收备注'), 'acceptance_at': ('Acceptance time', '验收时间'),
 'warranty_help': ('Warranty request is a draft; merchant adjudication and refund are not integrated.', '保修请求仍是草稿，尚未接入商家裁决或退款。'),
 'inspect_connection': ('Inspect shared connection', '检查公共连接'), 'replace': ('Out-of-warranty replacement / service', '过保替换或服务'),
 'observe': ('Continue observing', '继续观察'), 'warranty': ('Warranty request draft', '保修申请草稿'),
 'shared_connection': ('Shared-connection evidence', '公共连接线索'), 'reading_anomaly': ('Reading anomaly to review', '待读数复核'),
 'normal': ('No anomaly indicated', '当前未提示异常'), 'insufficient_data': ('Insufficient observations', '观测不足'),
 'checks': ('Recorded checks', '已记录检查'), 'check': ('Check', '检查'), 'status': ('State', '状态'),
 'value': ('Observed value', '观测值'), 'rule': ('Required comparison', '要求比较'),
 'unit': ('Unit', '单位'),
 'versions': ('Evidence and decision versions', '证据与决定版本'),
 'tracked': ('Version tracking began with this case. Only recorded updates are listed.', '版本跟踪随本案开始，仅列出实际记录的更新。'),
 'legacy': ('Earlier records predate version tracking. Their original update times and earlier versions are unknown; no history has been reconstructed.', '较早记录生成于版本跟踪之前，其原始更新时间和更早版本未知；没有补造历史。'),
 'no_versions': ('No structured evidence versions have been recorded.', '尚未记录结构化证据版本。'),
 'version': ('Version', '版本'), 'recorded_at': ('Recorded at', '记录时间'),
 'action': ('Update', '更新类型'), 'review': ('Human review updated', '人工复核更新'),
 'submit_recovery': ('Recovery evidence updated', '恢复证据更新'), 'verify_repair': ('Human acceptance recorded', '人工验收记录'),
 'before': ('Before this update', '本次更新之前'), 'after': ('After this update', '本次更新之后'),
 'legacy_before': ('The prior state below was observed when this update was made. Its original event time is unknown.', '下方旧状态是在本次更新时留存，其原始事件时间未知。'),
 'evidence_hash': ('Case-evidence SHA-256', '案件证据 SHA-256'), 'after_hash': ('Updated-state SHA-256', '更新后状态 SHA-256'),
 'hash_note': ('Checksums identify saved content; they do not authenticate a person or certify a physical repair.', '摘要用于识别保存内容，不认证操作者身份，也不认证实际维修。'),
 'original': ('Original source wording', '来源原文'), 'synthetic_fixture': ('Deterministic synthetic fixture', '确定性合成测试场景'),
 'recovered': ('Synthetic recovery example', '合成恢复示例'), 'still_faulty': ('Synthetic persistent-fault example', '合成持续故障示例'),
 'scenario_insufficient': ('Synthetic incomplete-evidence example', '合成证据不足示例'),
 'ai': ('AI evidence', 'AI 证据'), 'ai_current': ('Current AI result', '当前 AI 结果'),
 'ai_bound': ('AI evidence recorded with this human review', '本次人工复核绑定的 AI 证据'),
 'ai_unbound': ('No AI evidence was bound to this human decision. A current result does not retroactively support an earlier decision.', '这份人工决定没有绑定 AI 证据；当前结果不补作过去决定的依据。'),
 'ai_boundary': ('AI results are inspection leads. They do not establish the cause of a fault, decide warranty, certify repair or authorize a transaction.', 'AI 结果用于辅助排查，不证明故障原因，不裁决保修、不认证维修，也不批准交易。'),
 'ai_ran': ('The recorded local model inference completed. Its training data was synthetic; this is not field validation or a live run of the research LSTM.', '已记录本地模型实际推断结果；训练数据为合成数据，不代表现场验证，也不是研究 LSTM 的实时运行。'),
 'ai_not_ready': ('A usable model result is not recorded here. No successful inference is inferred from missing information.', '此处没有记录可用模型结果；不会把缺少信息视为推断成功。'),
 'ai_changed': ('The current AI result differs from the review snapshot. The bound snapshot below remains the evidence for that recorded review.', '当前 AI 结果与复核快照不同；下方绑定快照仍是当时复核所依据的证据。'),
 'ai_details': ('Model identifiers and original signal sources', '模型标识与信号原始来源'),
 'ai_model': ('Model', '模型'), 'ai_training': ('Training data', '训练数据'),
 'ai_synthetic': ('Synthetic only', '仅合成数据'), 'ai_pattern': ('Inspection lead', '排查线索'),
 'ai_model_hash': ('Model SHA-256', '模型 SHA-256'), 'ai_input_hash': ('Input SHA-256', '输入 SHA-256'),
 'ai_evidence_hash': ('AI-evidence SHA-256', 'AI 证据 SHA-256'),
 'ai_signal': ('Signal', '信号'), 'ai_device': ('Original device ID', '原始设备编号'),
 'ai_start': ('Source window start', '来源时间窗起点'), 'ai_end': ('Source window end', '来源时间窗终点'),
 'ai_no_sources': ('No signal source ranges were recorded.', '未记录信号来源时间范围。'),
 'ai_ready': ('Inference result recorded', '已记录推断结果'),
 'ai_unavailable': ('Model unavailable', '模型不可用'), 'ai_insufficient': ('Inputs insufficient', '输入不足'),
 'ai_shared_dropout': ('Several devices stopped reporting together; inspect their shared connection.', '多台设备同时停止上报；先检查公共连接。'),
 'ai_persistent_shift': ('A persistent change from earlier readings needs inspection; its cause is not established.', '读数持续偏离先前水平，需要检查；原因尚未确定。'),
 'ai_stuck': ('Readings stayed unusually constant; check the sensor and its local conditions.', '读数异常稳定；需要检查传感器及其周围条件。'),
 'ai_normal': ('No tested anomaly pattern stood out.', '未发现明显符合已测试异常模式的线索。'),
 'ai_single_dropout': ('One device stopped reporting; inspect its connection and power.', '一台设备停止上报；需要检查连接和供电。'),
 'ai_dropout': ('Reporting gaps need investigation; the cause is unknown.', '上报中断需要排查；原因未知。'),
 'ai_disagreement': ('Evidence sources disagree; further human inspection is needed.', '不同证据存在分歧，需要进一步人工检查。'),
 'calibration_points': ('Calibration observations', '校准观测数'),
 'detection_observed_points': ('Observed detection samples', '检测窗口有效观测数'),
 'median_residual_vwc': ('Median difference from baseline', '相对基线的中位差值'),
 'flat_duration_hours': ('Unchanged-reading duration', '读数不变时长'),
 'trailing_missing_hours': ('Trailing reporting gap', '窗口末端上报缺口'),
 'historical_noise_vwc': ('Historical reading variation', '历史读数波动'),
 'count': ('observations', '个观测'), 'percentage_points': ('percentage points', '百分点'), 'hours': ('hours', '小时'),
}


TEXT.update({
 'observation_window': ('Observation window', '观测时间窗'), 'paired_samples': ('Paired samples', '配对样本'),
 'link_samples': ('Connection observations', '连接观测'), 'link_success_ratio': ('Connection success ratio', '连接成功比例'),
 'reference_variation': ('Reference variation', '参考变化范围'), 'mean_absolute_error': ('Mean absolute error', '平均绝对误差'),
 'max_absolute_error': ('Maximum absolute error', '最大绝对误差'), 'sensor_variation': ('Probe variation', '探头变化范围'),
 'create_order': ('Create authorization order', '创建授权订单'), 'authorize': ('Verify authorization', '核验授权'),
 'capture': ('Charge approved amount', '扣取已批准金额'), 'void': ('Void authorization', '撤销授权'),
 'reconcile': ('Query transaction', '查询交易'), 'redacted': ('[redacted]', '[已隐去]'),
 'path_omitted': ('[local path omitted]', '[已隐去本机路径]'),
 'hourly_window': ('hourly window', '逐小时窗口'), 'ratio': ('ratio', '比例'),
 'sample_unit': ('samples', '个样本'), 'true': ('Yes', '是'), 'false': ('No', '否'),
})

_SENSITIVE_KEYS = {'csrf','client_id','client_secret','access_token','refresh_token','password','secret','api_key','credentials','authorization','authorization_header'}
_PATHS = re.compile(r"[A-Za-z]:[\\/][^\r\n<>\"']+|\\\\[^\s<>\"']+|(?<![\w:/<])/(?:[\w.-]+/)*[\w.-]+")
_ASSIGNMENT = re.compile(r"(?i)\b(?:csrf|client[_ -]?(?:secret|id)|access[_ -]?token|refresh[_ -]?token|password|api[_ -]?key)\b\s*[:=]\s*(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)")
_BEARER = re.compile(r"(?i)\bBearer\s+[^\s,;<>]+")

def _private_values(value):
    result = set()
    def visit(node, sensitive=False):
        if isinstance(node, dict):
            for key, child in node.items():
                lowered = str(key).lower().replace('-', '_')
                visit(child, sensitive or lowered in _SENSITIVE_KEYS or lowered.endswith('_request_id'))
        elif isinstance(node, list):
            for child in node: visit(child, sensitive)
        elif sensitive and isinstance(node, str) and node:
            result.add(node)
    visit(value)
    return result

def _dict(value):
    return value if isinstance(value, dict) else {}

def render_case_report(case, snapshot, language='en') -> str:
    """Render allowlisted fields only; do not mutate inputs or infer missing history."""
    locale = normalize_locale(language, default='en')
    def t(key):
        if locale in ('es','fr','pt'):
            return REPORT_EXTRA.get(key, {}).get(locale, key)
        return TEXT.get(key, (key,key))[1 if locale == 'zh-CN' else 0]
    case, state = _dict(case), _dict(snapshot)
    secret_values = sorted(_private_values([case,state]), key=len, reverse=True)
    def clean(value):
        if value is None: return t('missing')
        if not isinstance(value, (str,int,float,bool)): return t('missing')
        text = str(value)
        for secret in secret_values: text=text.replace(secret,t('redacted'))
        return _BEARER.sub(t('redacted'), _ASSIGNMENT.sub(t('redacted'), _PATHS.sub(t('path_omitted'),text)))
    def e(value): return escape(clean(value), quote=True)
    def p(value, cls=''): return '<p'+(' class="'+cls+'"' if cls else '')+'>'+e(value)+'</p>'
    def heading(level, text): return '<h'+str(level)+'>'+e(text)+'</h'+str(level)+'>'
    def table(items):
        return '<table class="pairs"><tbody>'+''.join('<tr><th scope="row">'+e(label)+'</th><td class="note">'+e(value)+'</td></tr>' for label,value in items)+'</tbody></table>'
    def status(value):
        return t(value) if isinstance(value,str) and value in TEXT else clean(value)
    def recovery_summary(recovery):
        recovery=_dict(recovery)
        return status(recovery.get('status')) if recovery else t('missing')
    def decision_summary(review):
        review=_dict(review)
        return status(review.get('decision')) if review else t('missing')
    def ai_state(evidence):
        evidence = _dict(evidence)
        return t('ai_' + evidence['status']) if evidence.get('status') in ('ready','unavailable','insufficient') else t('missing')
    def ai_pattern(evidence):
        evidence = _dict(evidence)
        code = evidence.get('summary_code') or evidence.get('pattern')
        return t('ai_' + code) if isinstance(code,str) and 'ai_' + code in TEXT else clean(code)
    def ai_identity(evidence):
        evidence = _dict(evidence); model = _dict(evidence.get('model'))
        return (evidence.get('status'), model.get('id'), model.get('sha256'), evidence.get('inputs_sha256'), evidence.get('evidence_sha256'))
    def ai_block(evidence, title):
        evidence = _dict(evidence); model = _dict(evidence.get('model'))
        result = heading(3,title) + table([(t('status'),ai_state(evidence)),(t('ai_pattern'),ai_pattern(evidence))])
        if evidence.get('status') == 'ready' and model.get('training_data') == 'synthetic':
            result += p(t('ai_ran'))
        else:
            result += p(t('ai_not_ready'))
        result += '<details class="ai-details"><summary>'+e(t('ai_details'))+'</summary>'
        result += table([(t('ai_model'),model.get('id')),(t('ai_training'),t('ai_synthetic') if model.get('training_data') == 'synthetic' else model.get('training_data')),
            (t('ai_model_hash'),model.get('sha256')),(t('ai_input_hash'),evidence.get('inputs_sha256')),(t('ai_evidence_hash'),evidence.get('evidence_sha256'))])
        signals = evidence.get('signals')
        signals = [item for item in signals if isinstance(item,dict)] if isinstance(signals,list) else []
        if signals:
            result += '<table><thead><tr>'+''.join('<th>'+e(t(key))+'</th>' for key in ('ai_signal','value','unit','ai_device','ai_start','ai_end'))+'</tr></thead><tbody>'
            for signal in signals:
                source = _dict(signal.get('source_range'))
                fields = [status(signal.get('code')), signal.get('value'), status(signal.get('unit')), signal.get('device_id'), source.get('start'), source.get('end')]
                result += '<tr>'+''.join('<td>'+e(value)+'</td>' for value in fields)+'</tr>'
            result += '</tbody></table>'
        else:
            result += p(t('ai_no_sources'))
        return result + '</details>'
    def evidence_state(value, title):
        value=_dict(value); review=_dict(value.get('review')); recovery=_dict(value.get('recovery')); acceptance=_dict(recovery.get('human_review'))
        return heading(3,title)+table([
            (t('decision'),decision_summary(review)),(t('note'),review.get('note')),
            (t('recovery'),recovery_summary(recovery)),(t('scenario'),status(recovery.get('scenario'))),
            (t('samples'),recovery.get('sample_count')),(t('repair'),status(value.get('repair'))),
            (t('acceptance_note'),acceptance.get('note')),(t('acceptance_at'),acceptance.get('at')),
            (t('ai'),ai_state(value.get('ai_review'))),(t('ai_pattern'),ai_pattern(value.get('ai_review'))),
            (t('ai_model'),_dict(_dict(value.get('ai_review')).get('model')).get('id')),
            (t('ai_input_hash'),_dict(value.get('ai_review')).get('inputs_sha256')),
            (t('ai_evidence_hash'),_dict(value.get('ai_review')).get('evidence_sha256')),
        ])
    display=localize_case(case,locale)
    review=_dict(state.get('review')); quote=_dict(state.get('quote')); payment=_dict(state.get('payment'))
    recovery=_dict(state.get('recovery')); acceptance=_dict(recovery.get('human_review'))
    body=[heading(1,t('title')),table([(t('case'),case.get('id')),(t('case_title'),display.get('title'))]),
          p(t('synthetic') if case.get('provenance')=='synthetic' else t('unknown_data'),'notice'),
          p(t('ai_boundary') if 'ai' in case or state.get('ai_review') else t('baseline')),p(t('separate'),'notice'),p(t('redaction'),'muted')]
    payment_status=payment.get('status')
    body += [heading(2,t('overview')),table([
        (t('decision'),decision_summary(review)),(t('approved'),t('yes') if state.get('approved') is True else t('no')),
        (t('payment'),t('payment_pending') if payment_status=='pending' else status(payment_status)),
        (t('mode'),status(payment.get('mode'))),(t('recovery'),recovery_summary(recovery)),
        (t('acceptance'),status(state.get('repair','unverified'))),
    ])]
    if review.get('decision')=='warranty':body.append(p(t('warranty_help'),'notice'))
    body += [heading(2,t('decision')),table([(t('decision'),decision_summary(review)),(t('note'),review.get('note'))])]
    bound_ai = _dict(state.get('ai_review')); current_ai = _dict(case.get('ai'))
    body += [heading(2,t('ai'))]
    if bound_ai:
        body.append(ai_block(bound_ai,t('ai_bound')))
        if 'ai' in case and ai_identity(current_ai) != ai_identity(bound_ai):
            body += [p(t('ai_changed'),'notice'),table([(t('ai_current'),ai_state(current_ai)),(t('ai_pattern'),ai_pattern(current_ai))])]
    else:
        body.append(p(t('ai_unbound'),'notice'))
        if 'ai' in case:
            body.append(ai_block(current_ai,t('ai_current')))
    analysis=_dict(display.get('analysis'))
    body += [heading(2,t('analysis')),table([(t('category'),status(analysis.get('category'))),(t('summary'),analysis.get('summary')),(t('method'),analysis.get('method'))])]
    if isinstance(analysis.get('evidence'),list):body.append('<ul>'+''.join('<li>'+e(item)+'</li>' for item in analysis['evidence'] if isinstance(item,str))+'</ul>')
    body += [heading(2,t('quote')),table([(t(key),quote.get(field)) for key,field in [('quote_version','version'),('item','sku'),('amount','amount'),('currency','currency'),('quote_at','approved_at')]]+[(t('seller'),status(quote.get('seller_role'))),(t('buyer'),status(quote.get('buyer_role')))])]
    body += [heading(2,t('payment')),table([(t('mode'),status(payment.get('mode'))),(t('status'),t('payment_pending') if payment_status=='pending' else status(payment_status))]+[(t(key),payment.get(key)) for key in ('intent','amount','currency','order_id','authorization_id','capture_id','record_id')])]
    if payment and payment.get('intent')!='AUTHORIZE':body.append(p(t('legacy_payment'),'notice'))
    pending=_dict(state.get('pending_operation'))
    if pending:body += [heading(3,t('pending')),table([(t('pending_action'),status(pending.get('action'))),(t('started_at'),pending.get('started_at'))])]
    body += [heading(2,t('recovery')),table([(t('status'),recovery_summary(recovery)),(t('source'),status(recovery.get('source'))),(t('scenario'),t('scenario_insufficient') if recovery.get('scenario')=='insufficient' else status(recovery.get('scenario'))),(t('samples'),recovery.get('sample_count'))])]
    checks=recovery.get('checks')
    if isinstance(checks,list) and checks:
        body.append(heading(3,t('checks'))+'<table><thead><tr>'+''.join('<th>'+e(t(k))+'</th>' for k in ('check','status','value','rule','unit'))+'</tr></thead><tbody>')
        for check in checks:
            check=_dict(check)
            observed = check.get('value'); threshold = check.get('threshold')
            observed = t('true' if observed else 'false') if isinstance(observed,bool) else observed
            threshold = t('true' if threshold else 'false') if isinstance(threshold,bool) else threshold
            operator = {'eq':'=', 'gte':'≥', 'lte':'≤', 'gt':'>'}.get(check.get('operator'),clean(check.get('operator')))
            unit = t('sample_unit') if check.get('unit') == 'samples' else status(check.get('unit'))
            fields=[status(check.get('code')),status(check.get('status')),observed,operator+' '+clean(threshold),unit]
            body.append('<tr>'+''.join('<td>'+e(value)+'</td>' for value in fields)+'</tr>')
        body.append('</tbody></table>')
    body += [heading(2,t('acceptance')),table([(t('repair'),status(state.get('repair','unverified'))),(t('acceptance_note'),acceptance.get('note')),(t('acceptance_at'),acceptance.get('at'))])]
    versions=state.get('evidence_history'); versions=versions if isinstance(versions,list) else []
    body += [heading(2,t('versions')),p(t('tracked') if state.get('evidence_history_origin')=='tracked_from_start' else t('legacy'))]
    if not versions:body.append(p(t('no_versions')))
    for item in versions:
        item=_dict(item)
        body.append('<article class="version">'+heading(3,t('version')+' '+clean(item.get('version'))))
        body.append(table([(t('recorded_at'),item.get('recorded_at')),(t('action'),status(item.get('action')))]))
        if item.get('before_origin')=='legacy_state_observed_at_update':body.append(p(t('legacy_before'),'notice'))
        body.append(evidence_state(item.get('before'),t('before')))
        body.append(evidence_state(item.get('after'),t('after')))
        body.append(table([(t('evidence_hash'),item.get('case_evidence_sha256')),(t('after_hash'),item.get('after_sha256'))]))
        body.append('</article>')
    body.append(p(t('hash_note'),'muted'))
    body.append('<footer>'+e(t('permission'))+'</footer>')
    return '<!doctype html><html lang="'+locale+'"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>'+e(t('title'))+'</title><style>'+REPORT_CSS+'</style></head><body>'+''.join(body)+'</body></html>'
