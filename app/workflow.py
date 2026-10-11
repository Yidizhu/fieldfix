"""Single-operator prototype: immutable quote, human recovery review, separate settlement."""
from contextlib import closing
from copy import deepcopy
import hashlib
from datetime import datetime, timezone, timedelta
import json
import re
import sqlite3
import threading
import uuid
from recovery import evaluate_recovery
from paypal import parse_time, PaymentPreflightError


class WorkflowError(Exception):
    pass


def now():
    return datetime.now(timezone.utc)


class Workflow:
    def __init__(self, db_path, cases, paypal):
        self.db_path, self.cases, self.paypal = str(db_path), {c['id']: c for c in cases}, paypal
        self.lock = threading.RLock()
        with closing(sqlite3.connect(self.db_path)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
            for case_id in self.cases:
                row = db.execute('SELECT data FROM cases WHERE id=?', (case_id,)).fetchone()
                state = json.loads(row[0]) if row else {
                    'review': None, 'approved': False, 'payment': None,
                    'repair': 'unverified', 'history': []}
                for key in ('quote', 'recovery', 'pending_operation', 'ai_review'):
                    state.setdefault(key, None)
                state.setdefault('evidence_history', [])
                state.setdefault('evidence_history_origin', 'legacy_unversioned' if row else 'tracked_from_start')
                for action in ('create', 'authorize', 'capture', 'void'):
                    state.setdefault(action + '_request_id', str(uuid.uuid4()))
                state['workflow_version'] = 3
                db.execute('INSERT OR REPLACE INTO cases VALUES (?,?)', (case_id, json.dumps(state, ensure_ascii=False)))

    def _get(self, case_id):
        if case_id not in self.cases:
            raise WorkflowError('案件不存在。')
        with closing(sqlite3.connect(self.db_path)) as db:
            return json.loads(db.execute('SELECT data FROM cases WHERE id=?', (case_id,)).fetchone()[0])

    def _save(self, case_id, state):
        with closing(sqlite3.connect(self.db_path)) as db, db:
            db.execute('UPDATE cases SET data=? WHERE id=?', (json.dumps(state, ensure_ascii=False), case_id))

    def snapshot(self, case_id):
        with self.lock:
            return {k: v for k, v in self._get(case_id).items() if not k.endswith('request_id')}

    def _event(self, state, text):
        state['history'].append({'at': now().isoformat(), 'text': text})

    @staticmethod
    def _evidence_state(state):
        # Copy only evidence/decision fields, never payment credentials or request IDs.
        return deepcopy({key: state.get(key) for key in ('review', 'recovery', 'repair', 'approved', 'quote', 'ai_review')})

    def _record_evidence_change(self, case_id, state, action, before):
        after = self._evidence_state(state)
        if action == 'verify_repair' and before == after:
            return  # A repeated acceptance is not a new human decision.
        history = state['evidence_history']
        case = self.cases[case_id]
        source = deepcopy({key: case.get(key) for key in ('id', 'provenance', 'analysis', 'series', 'ai')})
        canonical = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
        history.append({
            'version': len(history) + 1,
            'recorded_at': now().isoformat(),
            'action': action,
            'before_origin': 'legacy_state_observed_at_update' if not history and state['evidence_history_origin'] == 'legacy_unversioned' else 'tracked_state',
            'before': deepcopy(before),
            'after': after,
            'case_evidence': source,
            'case_evidence_sha256': hashlib.sha256(canonical(source)).hexdigest(),
            'after_sha256': hashlib.sha256(canonical(after)).hexdigest(),
        })

    @staticmethod
    def _ai_identity(evidence):
        """Validate the trusted server result; hashes identify evidence, not truth."""
        if not isinstance(evidence, dict) or evidence.get('status') != 'ready':
            raise WorkflowError('AI 证据尚未就绪，不能进入替换、保修或新交易；请先补齐证据。')
        model = evidence.get('model')
        if not isinstance(model, dict) or not isinstance(model.get('id'), str) or not model['id'].strip():
            raise WorkflowError('AI 证据标识不完整，不能进入替换、保修或新交易。')
        hashes = (model.get('sha256'), evidence.get('inputs_sha256'), evidence.get('evidence_sha256'))
        if any(not isinstance(value, str) or re.fullmatch(r'[0-9a-fA-F]{64}', value) is None for value in hashes):
            raise WorkflowError('AI 证据标识不完整，不能进入替换、保修或新交易。')
        return (model['id'], *(value.lower() for value in hashes))

    def _require_ai_binding(self, case_id, state):
        case = self.cases[case_id]
        if 'ai' not in case:
            return  # Existing baseline-only cases remain compatible.
        current = self._ai_identity(case['ai'])
        try:
            reviewed = self._ai_identity(state.get('ai_review'))
        except WorkflowError:
            raise WorkflowError('当前人工复核没有绑定可用 AI 证据；请重新复核后再批准新交易。') from None
        if reviewed != current:
            raise WorkflowError('AI 模型或案件证据已变化；请重新进行人工复核后再批准新交易。')

    def _approved(self, state):
        if not state['approved'] or not state['review'] or state['review']['decision'] != 'replace' or not state['quote']:
            raise WorkflowError('未通过人工复核与报价批准，不能执行交易。')

    def _network(self, case_id, state, action, call):
        pending = state['pending_operation']
        if pending:
            started = parse_time(pending.get('started_at'))
            if not started or now() - started >= timedelta(hours=5):
                raise WorkflowError('原请求已超过安全重试期限；请核对交易或人工处理，不能新建重复订单。')
        else:
            state['pending_operation'] = {'action': action, 'started_at': now().isoformat()}
            self._event(state, 'Sandbox 请求已开始；结果未核实前禁止执行相反操作。')
            self._save(case_id, state)  # Survives timeout/restart. Never regenerate request ID.
        try:
            result = call()
        except PaymentPreflightError:
            if not pending:
                state['pending_operation'] = None
                self._save(case_id, state)
            raise
        state['payment'] = dict(state['payment'] or {}, **result)
        if result['status'] == 'pending':
            # Provider pending capture/authorization is unresolved, not a success.
            self._save(case_id, state)
        else:
            state['pending_operation'] = None
        return result

    def act(self, case_id, action, body):
        with self.lock:
            state = self._get(case_id)
            payment = state['payment']
            if payment and payment.get('intent') != 'AUTHORIZE':
                raise WorkflowError('旧版交易记录仅供查阅，请使用新演示案件。')
            evidence_before = self._evidence_state(state) if action in ('review', 'submit_recovery', 'verify_repair') else None
            pending = state['pending_operation']
            if pending and action not in (pending['action'], 'reconcile'):
                raise WorkflowError('上一笔请求结果尚未确定；请重试同一操作或核对原交易。')

            if action == 'review':
                if payment:
                    raise WorkflowError('已有交易记录，不能覆盖前序复核。')
                decision, note = body.get('decision'), str(body.get('note', '')).strip()
                if not 8 <= len(note) <= 1000:
                    raise WorkflowError('请填写 8–1000 字的检查记录。')
                if decision not in ('inspect_connection', 'replace', 'observe', 'warranty'):
                    raise WorkflowError('请选择有效处理方式。')
                if decision in ('replace', 'warranty') and self.cases[case_id]['analysis']['category'] != 'reading_anomaly':
                    raise WorkflowError('当前证据不支持进入单支更换或保修流程。')
                if body.get('confirmed') is not True:
                    raise WorkflowError('需要明确确认这是演练中的人工检查记录。')
                trusted_ai = self.cases[case_id].get('ai')
                if decision in ('replace', 'warranty') and 'ai' in self.cases[case_id]:
                    self._ai_identity(trusted_ai)
                state.update(review={'decision': decision, 'note': note, 'simulated': True},
                             approved=False, quote=None, recovery=None, repair='unverified',
                             ai_review=deepcopy(trusted_ai))
                self._event(state, '人工复核已记录（模拟现场检查）：' + note)

            elif action == 'approve':
                if not state['review'] or state['review']['decision'] != 'replace':
                    raise WorkflowError('先记录人工检查并选择过保替换。')
                if body.get('confirmed') is not True:
                    raise WorkflowError('报价需要明确批准。')
                if not payment:
                    self._require_ai_binding(case_id, state)
                if not state['approved']:
                    state['approved'] = True
                    state['quote'] = {'case_id': case_id, 'version': 1, 'sku': 'FF-Soil-01',
                        'amount': '25.00', 'currency': 'NZD', 'seller_role': 'monitoring_service_provider',
                        'buyer_role': 'farm', 'synthetic': True, 'approved_at': now().isoformat(),
                        'terms': 'Authorize first; capture only after simulated recovery and human confirmation. No real goods or service.'}
                    self._event(state, '已批准模拟服务报价 NZD 25.00；监测服务商为卖方，农场为买方。')

            elif action in ('rehearse', 'create_order'):
                self._approved(state)
                mode = 'local_rehearsal' if action == 'rehearse' else 'paypal_sandbox'
                if payment and payment.get('mode') != mode:
                    raise WorkflowError('本地演练与 Sandbox 交易不能混用，请使用独立测试案件。')
                if not payment:
                    # A pending create is an existing attempt with its original idempotency key.
                    # Allow its recovery even if current inference is unavailable; never start a new attempt.
                    if not pending:
                        self._require_ai_binding(case_id, state)
                    if action == 'rehearse':
                        state['payment'] = {'mode': mode, 'intent': 'AUTHORIZE', 'status': 'authorized',
                            'record_id': 'DEMO-' + uuid.uuid4().hex[:10], 'amount': state['quote']['amount'],
                            'currency': 'NZD', 'authorized_at': now().isoformat(),
                            'expires_at': (now() + timedelta(days=29)).isoformat()}
                        self._event(state, '本地授权演练已记录；未调用 PayPal，未冻结或扣取任何款项。')
                    else:
                        result = self._network(case_id, state, action, lambda: self.paypal.create(
                            case_id, state['quote']['amount'], state['create_request_id']))
                        state['payment'] = dict(result, mode=mode, intent='AUTHORIZE', amount=state['quote']['amount'], currency='NZD')
                        self._event(state, 'Sandbox 授权订单已创建，等待测试买家批准；尚未扣款。')

            elif action in ('authorize', 'capture', 'void', 'reconcile'):
                self._approved(state)
                if not payment:
                    raise WorkflowError('没有可核验的授权订单。')
                if action == 'capture':
                    if body.get('confirmed') is not True:
                        raise WorkflowError('扣款需要再次明确确认金额与恢复复核结果。')
                    if state['repair'] != 'verified_demo' or not state['recovery'] or state['recovery']['status'] != 'pass':
                        raise WorkflowError('恢复证据尚未通过检查和人工复核，禁止扣款。')
                    if payment['status'] not in ('authorized', 'completed', 'pending'):
                        raise WorkflowError('当前授权不可扣款。')
                elif action == 'void':
                    if body.get('confirmed') is not True:
                        raise WorkflowError('撤销授权需要明确确认。')
                    if payment['status'] not in ('authorized', 'voided'):
                        raise WorkflowError('当前授权不可撤销；请先核对是否已扣款。')
                if action == 'reconcile':
                    if payment['mode'] != 'paypal_sandbox':
                        raise WorkflowError('本地演练没有可查询的 PayPal 交易。')
                    result = self.paypal.reconcile(payment['order_id'], case_id, state['quote']['amount'], payment.get('authorization_id'), payment.get('capture_id'))
                    state['payment'] = dict(payment, **result)
                    expected = {'create_order': ('awaiting_buyer', 'authorized'), 'authorize': ('authorized',),
                                'capture': ('completed', 'denied'), 'void': ('voided',)}
                    if pending and result['status'] in expected.get(pending['action'], ()):
                        state['pending_operation'] = None
                    # terminal states cannot result in a second transaction via this case
                    if result['status'] in ('completed', 'voided', 'expired', 'denied'):
                        state['pending_operation'] = None
                    self._event(state, '已重新查询 Sandbox 原交易；付款状态与维修状态分别保留。')
                elif (action == 'authorize' and payment['status'] != 'awaiting_buyer' and not pending) or (action == 'capture' and payment['status'] == 'completed') or (action == 'void' and payment['status'] == 'voided'):
                    return self.snapshot(case_id)
                elif payment['mode'] == 'local_rehearsal':
                    if action == 'capture':
                        payment.update(status='completed', capture_id='DEMO-CAPTURE-' + uuid.uuid4().hex[:8])
                        self._event(state, '本地扣款演练已记录；未调用 PayPal，未发生真实或 Sandbox 付款。')
                    elif action == 'void':
                        payment['status'] = 'voided'
                        self._event(state, '本地撤销授权演练已记录；未调用 PayPal。')
                else:
                    if action == 'authorize':
                        call = lambda: self.paypal.authorize(payment['order_id'], case_id, state['quote']['amount'], state['authorize_request_id'])
                    else:
                        if not payment.get('authorization_id'):
                            raise WorkflowError('缺少已核验的授权编号。')
                        if action == 'capture':
                            def checkpoint(reference):
                                state['payment'].update(reference)
                                self._save(case_id, state)
                            call = lambda: self.paypal.capture_authorization(payment['order_id'], payment['authorization_id'], case_id,
                                state['quote']['amount'], state['capture_request_id'], checkpoint=checkpoint, capture_id=payment.get('capture_id'))
                        else:
                            call = lambda: self.paypal.void_authorization(payment['order_id'], payment['authorization_id'], case_id,
                                state['quote']['amount'], state['void_request_id'])
                    result = self._network(case_id, state, action, call)
                    events = {'authorized': 'Sandbox 授权已核验；款项暂时保留，尚未扣取。',
                        'completed': 'Sandbox 扣款已核验；这不代表真实设备已修复。',
                        'voided': 'Sandbox 授权已撤销；未执行扣款。',
                        'pending': 'Sandbox 仍在处理，尚不能确认扣款或授权完成。',
                        'expired': 'Sandbox 授权已过期，禁止继续扣款。',
                        'denied': 'Sandbox 拒绝本次交易，未记录为成功。'}
                    self._event(state, events.get(result['status'], 'Sandbox 状态已更新。'))

            elif action in ('submit_recovery', 'verify_repair'):
                if not state['review']:
                    raise WorkflowError('先完成案件复核。')
                if state['review']['decision'] == 'warranty':
                    raise WorkflowError('保修为申请草稿，尚未接入商家处理与验收。')
                if state['review']['decision'] == 'replace' and (not payment or payment['status'] != 'authorized'):
                    raise WorkflowError('请先完成授权；已结算或撤销的记录不可修改恢复证据。')
                if action == 'submit_recovery':
                    try:
                        evidence = evaluate_recovery(body.get('scenario'))
                    except (ValueError, TypeError):
                        raise WorkflowError('请选择有效的模拟恢复数据场景。') from None
                    state.update(recovery=evidence, repair='unverified')
                    self._event(state, '已检查模拟恢复数据；更换证据后需要重新进行人工复核。')
                else:
                    if not state['recovery'] or state['recovery']['status'] != 'pass':
                        raise WorkflowError('恢复证据尚未通过检查，不能确认恢复。')
                    note = str(body.get('note', '')).strip()
                    if not 8 <= len(note) <= 1000 or body.get('confirmed') is not True:
                        raise WorkflowError('请确认模拟复查并填写 8–1000 字观察记录。')
                    if state['repair'] != 'verified_demo':
                        state['repair'] = 'verified_demo'
                        state['recovery']['human_review'] = {'note': note, 'at': now().isoformat(), 'simulated': True}
                        self._event(state, '模拟恢复证据已由人复核，非真实维修：' + note)
            else:
                raise WorkflowError('操作不存在。')
            if evidence_before is not None:
                self._record_evidence_change(case_id, state, action, evidence_before)
            self._save(case_id, state)
            return self.snapshot(case_id)
