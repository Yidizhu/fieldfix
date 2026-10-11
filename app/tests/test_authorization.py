"""Authorization lifecycle tests: all provider responses are controlled fakes."""
import copy
import io
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paypal import PayPal, PaymentError


def auth(status='CREATED'):
    return {'id': 'AUTH123', 'status': status, 'amount': {'value': '25.00', 'currency_code': 'NZD'},
            'create_time': datetime.now(timezone.utc).isoformat(),
            'expiration_time': (datetime.now(timezone.utc) + timedelta(days=29)).isoformat()}


def order(with_auth=True, with_capture=False):
    unit = {'reference_id': 'B', 'custom_id': 'B', 'amount': {'value': '25.00', 'currency_code': 'NZD'}}
    if with_auth:
        unit['payments'] = {'authorizations': [auth()]}
    if with_capture:
        unit['payments']['captures'] = [{'id': 'CAP123'}]
    return {'id': 'ORDER123', 'intent': 'AUTHORIZE', 'status': 'COMPLETED' if with_auth else 'APPROVED', 'purchase_units': [unit]}


def capture(status='COMPLETED'):
    return {'id': 'CAP123', 'status': status, 'amount': {'value': '25.00', 'currency_code': 'NZD'},
            'supplementary_data': {'related_ids': {'order_id': 'ORDER123', 'authorization_id': 'AUTH123'}}}


class AuthorizationAdapterTests(unittest.TestCase):
    def setUp(self):
        self.adapter = PayPal('http://127.0.0.1:8766')
        self.token = patch.object(self.adapter, '_token', return_value='fake-token')
        self.token.start()
        self.addCleanup(self.token.stop)

    def test_create_requests_authorize_and_fixed_sandbox_return(self):
        response = {'id': 'ORDER123', 'links': [{'rel': 'payer-action', 'href': 'https://www.sandbox.paypal.com/checkoutnow?token=ORDER123'}]}
        with patch.object(self.adapter, '_json', return_value=response) as request:
            result = self.adapter.create('B', '25.00', 'stable-key')
        payload = request.call_args.args[1]
        self.assertEqual(payload['intent'], 'AUTHORIZE')
        self.assertEqual(payload['purchase_units'][0]['amount']['currency_code'], 'NZD')
        self.assertEqual(request.call_args.args[-1], 'stable-key')
        self.assertEqual(result['status'], 'awaiting_buyer')

    def test_authorize_never_captures_and_rechecks_provider(self):
        with patch.object(self.adapter, '_json', side_effect=[order(False), {}, order(), auth()]) as request:
            result = self.adapter.authorize('ORDER123', 'B', '25.00', 'AUTH-KEY')
        self.assertEqual(result['status'], 'authorized')
        self.assertEqual(result['authorization_id'], 'AUTH123')
        self.assertFalse(any('/capture' in call.args[0] for call in request.call_args_list))
        self.assertEqual(request.call_args_list[1].args[-1], 'AUTH-KEY')

    def test_buyer_not_approved_cannot_authorize(self):
        data = order(False)
        data['status'] = 'PAYER_ACTION_REQUIRED'
        with patch.object(self.adapter, '_json', return_value=data) as request:
            with self.assertRaises(PaymentError):
                self.adapter.authorize('ORDER123', 'B', '25.00', 'AUTH-KEY')
        self.assertEqual(request.call_count, 1)

    def test_existing_authorization_is_queried_without_second_post(self):
        with patch.object(self.adapter, '_json', side_effect=[order(), order(), auth()]) as request:
            result = self.adapter.authorize('ORDER123', 'B', '25.00', 'AUTH-KEY')
        self.assertEqual(result['status'], 'authorized')
        self.assertTrue(all(len(call.args) == 1 for call in request.call_args_list))

    def test_mismatched_order_prevents_authorization_side_effect(self):
        for key, value in [('id', 'OTHER'), ('intent', 'CAPTURE')]:
            data = order(False)
            data[key] = value
            with self.subTest(key=key), patch.object(self.adapter, '_json', return_value=data) as request:
                with self.assertRaises(PaymentError):
                    self.adapter.authorize('ORDER123', 'B', '25.00', 'AUTH-KEY')
                self.assertEqual(request.call_count, 1)

    def test_authorization_id_amount_currency_and_count_must_match(self):
        changes = [lambda d: d['purchase_units'][0]['payments']['authorizations'][0].update(id='OTHER'),
                   lambda d: d['purchase_units'][0]['payments']['authorizations'][0]['amount'].update(value='26'),
                   lambda d: d['purchase_units'][0]['payments']['authorizations'][0]['amount'].update(currency_code='USD'),
                   lambda d: d['purchase_units'][0]['payments']['authorizations'].append(auth())]
        for change in changes:
            data = order()
            change(data)
            with patch.object(self.adapter, '_json', return_value=data) as request:
                with self.assertRaises(PaymentError):
                    self.adapter.capture_authorization('ORDER123', 'AUTH123', 'B', '25.00', 'CAP-KEY')
                self.assertEqual(request.call_count, 1)

    def test_capture_uses_authorization_endpoint_and_verifies_get(self):
        with patch.object(self.adapter, '_json', side_effect=[order(), auth(), {'id': 'CAP123'}, capture()]) as request:
            result = self.adapter.capture_authorization('ORDER123', 'AUTH123', 'B', '25.00', 'CAP-KEY')
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(request.call_args_list[2].args[0], '/v2/payments/authorizations/AUTH123/capture')
        self.assertTrue(request.call_args_list[2].args[1]['final_capture'])
        self.assertEqual(request.call_args_list[2].args[-1], 'CAP-KEY')
        self.assertEqual(request.call_args_list[-1].args[0], '/v2/payments/captures/CAP123')

    def test_capture_pending_is_not_success_and_requery_does_not_capture_twice(self):
        for status, expected in [('PENDING', 'pending'), ('COMPLETED', 'completed'), ('DECLINED', 'denied')]:
            with self.subTest(status=status), patch.object(self.adapter, '_json', side_effect=[order(True, True), auth('CAPTURED'), capture(status)]) as request:
                result = self.adapter.capture_authorization('ORDER123', 'AUTH123', 'B', '25.00', 'CAP-KEY')
                self.assertEqual(result['status'], expected)
                self.assertEqual(request.call_count, 3)
                self.assertTrue(all(len(call.args) == 1 for call in request.call_args_list))

    def test_capture_mismatched_related_id_never_claims_success(self):
        data = capture()
        data['supplementary_data']['related_ids']['authorization_id'] = 'OTHER'
        with patch.object(self.adapter, '_json', side_effect=[order(), auth(), {'id': 'CAP123'}, data]):
            with self.assertRaises(PaymentError):
                self.adapter.capture_authorization('ORDER123', 'AUTH123', 'B', '25.00', 'CAP-KEY')

    def test_expiry_and_three_day_cutoff_block_capture(self):
        for mode in ('expiry', 'honor', 'missing'):
            data = auth()
            if mode == 'expiry':
                data['expiration_time'] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
            elif mode == 'honor':
                data['create_time'] = (datetime.now(timezone.utc) - timedelta(days=4)).isoformat()
            else:
                data.pop('expiration_time')
            with self.subTest(mode=mode), patch.object(self.adapter, '_json', side_effect=[order(), data]) as request:
                with self.assertRaises(PaymentError):
                    self.adapter.capture_authorization('ORDER123', 'AUTH123', 'B', '25.00', 'CAP-KEY')
                self.assertEqual(request.call_count, 2)

    def test_void_rechecks_and_cannot_void_captured_payment(self):
        with patch.object(self.adapter, '_json', side_effect=[order(), auth(), {}, order(), auth('VOIDED')]) as request:
            result = self.adapter.void_authorization('ORDER123', 'AUTH123', 'B', '25.00', 'VOID-KEY')
        self.assertEqual(result['status'], 'voided')
        self.assertEqual(request.call_args_list[2].args[0], '/v2/payments/authorizations/AUTH123/void')
        with patch.object(self.adapter, '_json', side_effect=[order(True, True), auth('CAPTURED'), capture()]) as request:
            with self.assertRaises(PaymentError):
                self.adapter.void_authorization('ORDER123', 'AUTH123', 'B', '25.00', 'VOID-KEY')
            self.assertEqual(request.call_count, 3)

    def test_void_idempotent_after_response_loss(self):
        with patch.object(self.adapter, '_json', side_effect=[order(), auth('VOIDED')]) as request:
            result = self.adapter.void_authorization('ORDER123', 'AUTH123', 'B', '25.00', 'VOID-KEY')
        self.assertEqual(result['status'], 'voided')
        self.assertEqual(request.call_count, 2)

    def test_http_204_is_valid_empty_response_and_hardcoded_sandbox(self):
        with patch('urllib.request.urlopen', return_value=io.BytesIO(b'')) as request:
            self.assertEqual(self.adapter._json('/v2/payments/authorizations/AUTH123/void', {}, 'fake-token', 'VOID-KEY'), {})
        self.assertTrue(request.call_args.args[0].full_url.startswith('https://api-m.sandbox.paypal.com/'))


if __name__ == '__main__':
    unittest.main()
