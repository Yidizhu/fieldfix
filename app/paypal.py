"""Sandbox-only adapter. Never accepts a live endpoint or exposes credentials."""
import base64
import json
import os
import urllib.request
import urllib.error
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone, timedelta

BASE = "https://api-m.sandbox.paypal.com"
class PaymentError(Exception):
    pass

class PaymentPreflightError(PaymentError):
    """This invocation has definitely not submitted a payment mutation."""
    pass

class PayPal:
    def __init__(self, return_base):
        self.return_base = return_base
        self.client_id = os.environ.get("PAYPAL_SANDBOX_CLIENT_ID", "")
        self.secret = os.environ.get("PAYPAL_SANDBOX_CLIENT_SECRET", "")

    @property
    def configured(self):
        return bool(self.client_id and self.secret)

    def _json(self, path, payload=None, token=None, request_id=None, oauth=False):
        headers = {"Accept": "application/json", "Prefer": "return=representation"}
        if oauth:
            auth = base64.b64encode(f"{self.client_id}:{self.secret}".encode()).decode()
            headers.update({"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"})
            body = b"grant_type=client_credentials"
        else:
            headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
            body = None if payload is None else json.dumps(payload).encode()
        if request_id:
            headers["PayPal-Request-Id"] = request_id
        req = urllib.request.Request(BASE + path, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                raw = response.read()
                return json.loads(raw) if raw else {}
        except (urllib.error.URLError, ValueError, TimeoutError, OSError):
            # Do not expose provider payloads, authorization, or secret-bearing objects.
            raise PaymentError("PayPal Sandbox 未完成请求。请检查配置或稍后重试；不要另建重复订单。") from None

    def _token(self):
        if not self.configured:
            raise PaymentPreflightError("尚未配置 PayPal Sandbox 测试凭据。")
        data = self._json("/v1/oauth2/token", oauth=True)
        if not data.get("access_token"):
            raise PaymentError("Sandbox 授权失败。")
        return data["access_token"]

    def create(self, case_id, amount, request_id):
        data = self._json("/v2/checkout/orders", {
            "intent": "AUTHORIZE",
            "purchase_units": [{"reference_id": case_id, "custom_id": case_id,
                "description": "FieldFix demo repair service: authorize now, capture after reviewed recovery. No real service.",
                "amount": {"currency_code": "NZD", "value": amount}}],
            "payment_source": {"paypal": {"experience_context": {
                "user_action": "PAY_NOW", "shipping_preference": "NO_SHIPPING",
                "return_url": self.return_base + "/?checkout=return",
                "cancel_url": self.return_base + "/?checkout=cancel"}}}
        }, self._token(), request_id)
        links = [x["href"] for x in data.get("links", []) if x.get("rel") in ("approve", "payer-action")]
        from urllib.parse import urlparse
        if not data.get("id") or not links or urlparse(links[0]).scheme != "https" or urlparse(links[0]).hostname not in ("www.sandbox.paypal.com", "sandbox.paypal.com"):
            raise PaymentError("Sandbox 未返回有效的测试付款链接。")
        return {"order_id": data["id"], "approval_url": links[0], "status": "awaiting_buyer", "intent": "AUTHORIZE"}

    def _order(self, order_id, case_id, amount, token):
        if not isinstance(order_id, str) or not order_id.isalnum():
            raise PaymentError("订单编号无效。")
        data = self._json('/v2/checkout/orders/' + order_id, token=token)
        unit = verify_order(data, order_id, case_id, amount)
        if data.get('intent') != 'AUTHORIZE':
            raise PaymentError('旧版直接扣款订单不可用于先授权后扣款流程。')
        return data, unit

    def authorize(self, order_id, case_id, amount, request_id):
        token = self._token()
        order, unit = self._order(order_id, case_id, amount, token)
        auths = unit.get('payments', {}).get('authorizations', [])
        if not auths:
            if order.get('status') != 'APPROVED':
                raise PaymentPreflightError('买家尚未批准此授权订单；尚未扣款。')
            self._json('/v2/checkout/orders/' + order_id + '/authorize', {}, token, request_id)
        return self._reconcile(order_id, case_id, amount, token)

    def reconcile(self, order_id, case_id, amount, authorization_id=None, capture_id=None):
        return self._reconcile(order_id, case_id, amount, self._token(), authorization_id, capture_id)

    def _reconcile(self, order_id, case_id, amount, token, authorization_id=None, capture_id=None):
        order, unit = self._order(order_id, case_id, amount, token)
        payment = {'order_id': order_id, 'intent': 'AUTHORIZE', 'mode': 'paypal_sandbox',
                   'amount': amount, 'currency': 'NZD'}
        auths = unit.get('payments', {}).get('authorizations', [])
        if not auths:
            if authorization_id or order.get('status') not in ('CREATED', 'SAVED', 'PAYER_ACTION_REQUIRED', 'APPROVED', 'VOIDED'):
                raise PaymentError('订单授权记录不完整，需要人工核查。')
            payment['status'] = 'voided' if order.get('status') == 'VOIDED' else 'awaiting_buyer'
            return payment
        if not isinstance(auths, list) or len(auths) != 1:
            raise PaymentError('订单授权记录不完整，需要人工核查。')
        embedded = auths[0]
        auth_id = embedded.get('id') if isinstance(embedded, dict) else None
        if not isinstance(auth_id, str) or not auth_id.isalnum() or (authorization_id and auth_id != authorization_id):
            raise PaymentError('授权编号与本案不一致，需要人工核查。')
        if not valid_amount(embedded.get('amount'), amount):
            raise PaymentError('授权金额或币种不符合预期。')
        auth = self._json('/v2/payments/authorizations/' + auth_id, token=token)
        if auth.get('id') != auth_id or not valid_amount(auth.get('amount'), amount):
            raise PaymentError('授权金额或币种不符合预期。')
        status = auth.get('status')
        statuses = {'CREATED': 'authorized', 'PENDING': 'pending', 'DENIED': 'denied',
                    'VOIDED': 'voided', 'EXPIRED': 'expired', 'CAPTURED': 'pending'}
        if status not in statuses:
            raise PaymentError('授权状态不适用于本演示，需要人工核查。')
        payment.update(authorization_id=auth_id, status=statuses[status],
                       expires_at=auth.get('expiration_time'), authorized_at=auth.get('create_time'))
        if status == 'CREATED':
            expiry = parse_time(auth.get('expiration_time'))
            created = parse_time(auth.get('create_time'))
            if not expiry or not created:
                raise PaymentError('授权有效期不完整，需要人工核查。')
            payment['capture_before'] = min(expiry, created + timedelta(days=3)).isoformat()
            if datetime.now(timezone.utc) >= expiry:
                payment['status'] = 'expired'
        captures = unit.get('payments', {}).get('captures', [])
        if captures or capture_id:
            if not isinstance(captures, list) or len(captures) > 1 or (captures and not isinstance(captures[0], dict)):
                raise PaymentError('付款记录数量不符合预期。')
            cap_id = captures[0].get('id') if captures else capture_id
            if capture_id and capture_id != cap_id:
                raise PaymentError('扣款记录不属于本案授权。')
            if not isinstance(cap_id, str) or not cap_id.isalnum():
                raise PaymentError('付款记录数量不符合预期。')
            cap = self._json('/v2/payments/captures/' + cap_id, token=token)
            payment.update(verify_authorized_capture(cap, cap_id, order_id, auth_id, amount))
        return payment

    def capture_authorization(self, order_id, authorization_id, case_id, amount, request_id, checkpoint=None, capture_id=None):
        token = self._token()
        current = self._reconcile(order_id, case_id, amount, token, authorization_id, capture_id)
        if current.get('capture_id'):
            return current  # A pending or completed capture must never be submitted twice.
        if current['status'] != 'authorized':
            raise PaymentPreflightError('授权尚不可扣款；请先核对交易状态。')
        cutoff = parse_time(current.get('capture_before'))
        if not cutoff or datetime.now(timezone.utc) >= cutoff:
            raise PaymentPreflightError('授权已超过本演示的三天扣款期限；请人工处理，不能自动重新授权。')
        cap = self._json('/v2/payments/authorizations/' + authorization_id + '/capture', {
            'amount': {'currency_code': 'NZD', 'value': amount}, 'final_capture': True,
            'note_to_payer': 'FieldFix Sandbox: simulated recovery reviewed; no real repair.'
        }, token, request_id)
        cap_id = cap.get('id')
        if not isinstance(cap_id, str) or not cap_id.isalnum():
            raise PaymentError('未取得可核查的扣款编号；请保持本案并核对原交易。')
        if checkpoint:
            checkpoint({'capture_id': cap_id, 'status': 'pending'})
        # Verify provider GET; successful POST alone never proves settlement.
        checked = self._json('/v2/payments/captures/' + cap_id, token=token)
        current.update(verify_authorized_capture(checked, cap_id, order_id, authorization_id, amount))
        return current

    def void_authorization(self, order_id, authorization_id, case_id, amount, request_id):
        token = self._token()
        current = self._reconcile(order_id, case_id, amount, token, authorization_id)
        if current['status'] == 'voided':
            return current
        if current['status'] != 'authorized' or current.get('capture_id'):
            raise PaymentPreflightError('当前授权不可撤销；请先核对是否已扣款。')
        self._json('/v2/payments/authorizations/' + authorization_id + '/void', {}, token, request_id)
        current = self._reconcile(order_id, case_id, amount, token, authorization_id)
        if current['status'] != 'voided':
            raise PaymentError('尚未核实授权撤销；请核对原交易，不要新建订单。')
        return current

    def capture(self, order_id, case_id, amount, request_id):
        # Retained for auditing old CAPTURE fixtures only; v0.3 workflow never calls this.
        if not order_id.isalnum():
            raise PaymentError("订单编号无效。")
        token = self._token()
        data = self._json("/v2/checkout/orders/" + order_id, token=token)
        if data.get("status") not in ("APPROVED", "COMPLETED"):
            raise PaymentError("买家尚未完成批准，订单未捕获。")
        verify_order(data, order_id, case_id, amount)
        if data.get("status") != "COMPLETED":
            self._json("/v2/checkout/orders/" + order_id + "/capture", {}, token, request_id)
            # Capture responses may be minimal; re-read full order details before verification.
            data = self._json("/v2/checkout/orders/" + order_id, token=token)
        return verify_capture(data, order_id, case_id, amount)

def parse_time(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return parsed if parsed.tzinfo else None
    except (ValueError, TypeError):
        return None

def verify_authorized_capture(cap, cap_id, order_id, auth_id, amount):
    if not isinstance(cap, dict) or cap.get('id') != cap_id or not valid_amount(cap.get('amount'), amount):
        raise PaymentError('付款金额、币种或状态不符合预期。')
    related = cap.get('supplementary_data', {}).get('related_ids', {})
    # Returned resources may omit related_ids, but must never contradict the verified order/POST.
    if related.get('order_id', order_id) != order_id or related.get('authorization_id', auth_id) != auth_id:
        raise PaymentError('扣款记录不属于本案授权。')
    mapped = {'COMPLETED': 'completed', 'PENDING': 'pending', 'DECLINED': 'denied', 'FAILED': 'denied'}
    if cap.get('status') not in mapped:
        raise PaymentError('付款状态尚未完成。')
    return {'capture_id': cap_id, 'status': mapped[cap['status']]}

def valid_amount(paid, expected):
    if not isinstance(paid, dict) or paid.get("currency_code") != "NZD":
        return False
    try:
        value, target = Decimal(str(paid.get("value"))), Decimal(str(expected))
        return value.is_finite() and target.is_finite() and value == target and target > 0
    except (InvalidOperation, ValueError, TypeError):
        return False


def verify_order(data, order_id, case_id, amount):
    if not isinstance(data, dict) or data.get("id") != order_id:
        raise PaymentError("订单编号不一致，需要人工复核。")
    units = data.get("purchase_units")
    if not isinstance(units, list) or len(units) != 1 or not isinstance(units[0], dict):
        raise PaymentError("订单明细数量不符合预期。")
    unit = units[0]
    if unit.get("reference_id") != case_id or unit.get("custom_id") != case_id:
        raise PaymentError("订单与案件不一致，需要人工复核。")
    if not valid_amount(unit.get("amount"), amount):
        raise PaymentError("订单金额或币种不符合预期。")
    return unit


def verify_capture(data, order_id, case_id, amount):
    unit = verify_order(data, order_id, case_id, amount)
    if data.get("status") != "COMPLETED":
        raise PaymentError("付款状态尚未完成。")
    payments = unit.get("payments")
    captures = payments.get("captures") if isinstance(payments, dict) else None
    if not isinstance(captures, list) or len(captures) != 1 or not isinstance(captures[0], dict):
        raise PaymentError("付款记录数量不符合预期。")
    cap = captures[0]
    if cap.get("status") != "COMPLETED" or not cap.get("id") or not valid_amount(cap.get("amount"), amount):
        raise PaymentError("付款金额、币种或状态不符合预期。")
    return {"status": "completed", "order_id": order_id, "capture_id": cap["id"], "amount": amount, "currency": "NZD", "mode": "paypal_sandbox"}
