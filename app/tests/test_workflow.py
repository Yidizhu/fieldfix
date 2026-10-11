"""Business-risk tests with fake provider and isolated SQLite."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paypal import PayPal, PaymentError, verify_capture
from workflow import Workflow, WorkflowError

CASES = [{'id': 'B', 'analysis': {'category': 'reading_anomaly'}},
         {'id': 'A', 'analysis': {'category': 'shared_outage'}},
         {'id': 'C', 'analysis': {'category': 'normal'}}]
NOTE = 'Simulated field inspection and recovery review for this demonstration.'


class FakePayPal:
    configured = True
    def __init__(self):
        self.calls, self.errors = [], {}
        self.remote = None

    def _call(self, action, args, result):
        self.calls.append((action, args))
        if self.errors.get(action):
            raise PaymentError('Uncertain provider result')
        self.remote = dict(result)
        return result

    def create(self, case_id, amount, key):
        return self._call('create', (case_id, amount, key), {'order_id': 'ORDER123', 'intent': 'AUTHORIZE', 'status': 'awaiting_buyer', 'approval_url': 'https://www.sandbox.paypal.com/checkoutnow?token=ORDER123'})

    def authorize(self, *args):
        return self._call('authorize', args, dict(self.remote, authorization_id='AUTH123', status='authorized'))

    def capture_authorization(self, *args, **kwargs):
        return self._call('capture', args, dict(self.remote, capture_id='CAPTURE123', status='completed'))

    def void_authorization(self, *args):
        return self._call('void', args, dict(self.remote, status='voided'))

    def reconcile(self, *args):
        self.calls.append(('reconcile', args))
        return dict(self.remote)


class WorkflowRiskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='fieldfix-v03-test-')
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / 'state.sqlite'
        self.adapter = FakePayPal()
        self.flow = Workflow(self.db, copy.deepcopy(CASES), self.adapter)

    def act(self, action, **body):
        return self.flow.act('B', action, body)

    def review(self):
        return self.act('review', decision='replace', note=NOTE, confirmed=True)

    def approve(self):
        self.review()
        return self.act('approve', confirmed=True)

    def authorize(self, local=False):
        self.approve()
        self.act('rehearse' if local else 'create_order')
        if not local:
            return self.act('authorize')
        return self.flow.snapshot('B')

    def recover(self):
        self.act('submit_recovery', scenario='recovered')
        return self.act('verify_repair', confirmed=True, note=NOTE)

    def test_all_transaction_actions_require_review_and_quote_approval(self):
        for stage in ('none', 'review'):
            if stage == 'review': self.review()
            for action in ('rehearse', 'create_order', 'authorize', 'capture', 'void'):
                with self.subTest(stage=stage, action=action), self.assertRaises(WorkflowError):
                    self.act(action, confirmed=True)
        self.assertEqual(self.adapter.calls, [])

    def test_approval_needs_review_and_boolean_confirmation(self):
        with self.assertRaises(WorkflowError): self.act('approve', confirmed=True)
        self.review()
        for value in (None, False, 'true', 1):
            with self.assertRaises(WorkflowError): self.act('approve', confirmed=value)
        self.assertFalse(self.flow.snapshot('B')['approved'])

    def test_outage_and_normal_cannot_enter_replacement_payment(self):
        for case_id in ('A', 'C'):
            with self.assertRaises(WorkflowError):
                self.flow.act(case_id, 'review', {'decision': 'replace', 'confirmed': True, 'note': NOTE})

    def test_quote_fixed_by_server_not_client_and_reapproval_is_idempotent(self):
        self.review()
        first = self.act('approve', confirmed=True, amount='0.01', currency='USD')
        self.assertEqual(first, self.act('approve', confirmed=True))
        self.assertEqual((first['quote']['amount'], first['quote']['currency']), ('25.00', 'NZD'))
        self.act('create_order', amount='1000', case_id='A')
        self.assertEqual(self.adapter.calls[0][1][:2], ('B', '25.00'))

    def test_review_change_revokes_quote_before_transaction(self):
        self.approve()
        changed = self.act('review', decision='observe', note=NOTE, confirmed=True)
        self.assertFalse(changed['approved'])
        self.assertIsNone(changed['quote'])
        with self.assertRaises(WorkflowError): self.act('create_order')

    def test_success_flow_separates_recovery_and_payment(self):
        authorized = self.authorize()
        self.assertEqual(authorized['payment']['status'], 'authorized')
        self.assertEqual(authorized['repair'], 'unverified')
        recovered = self.recover()
        self.assertEqual(recovered['repair'], 'verified_demo')
        self.assertEqual(recovered['payment']['status'], 'authorized')
        result = self.act('capture', confirmed=True)
        self.assertEqual(result['payment']['status'], 'completed')
        self.assertEqual(result['repair'], 'verified_demo')
        self.assertTrue(all('request_id' not in key for key in result))

    def test_no_capture_until_evidence_human_review_and_separate_confirmation(self):
        self.authorize()
        with self.assertRaises(WorkflowError): self.act('capture', confirmed=True)
        for scenario in ('still_faulty', 'insufficient'):
            self.act('submit_recovery', scenario=scenario)
            with self.assertRaises(WorkflowError): self.act('verify_repair', note=NOTE, confirmed=True)
            with self.assertRaises(WorkflowError): self.act('capture', confirmed=True)
        self.act('submit_recovery', scenario='recovered')
        with self.assertRaises(WorkflowError): self.act('capture', confirmed=True)
        self.act('verify_repair', note=NOTE, confirmed=True)
        for confirmed in (False, 1, 'true', None):
            with self.assertRaises(WorkflowError): self.act('capture', confirmed=confirmed)
        self.assertFalse(any(action == 'capture' for action, _ in self.adapter.calls))

    def test_changed_evidence_revokes_recovery_review(self):
        self.authorize()
        self.recover()
        result = self.act('submit_recovery', scenario='still_faulty')
        self.assertEqual(result['repair'], 'unverified')
        with self.assertRaises(WorkflowError): self.act('capture', confirmed=True)

    def test_local_rehearsal_full_flow_has_no_provider_calls(self):
        first = self.authorize(local=True)
        self.assertEqual(first, self.act('rehearse'))
        self.recover()
        result = self.act('capture', confirmed=True)
        self.assertEqual(result['payment']['mode'], 'local_rehearsal')
        self.assertTrue(result['payment']['capture_id'].startswith('DEMO-'))
        self.assertEqual(self.adapter.calls, [])

    def test_local_and_sandbox_cannot_mix(self):
        self.authorize(local=True)
        with self.assertRaises(WorkflowError): self.act('create_order')
        with self.assertRaises(WorkflowError): self.act('reconcile')

    def test_transaction_locks_review_and_completed_locks_recovery(self):
        self.authorize()
        with self.assertRaises(WorkflowError): self.review()
        self.recover()
        self.act('capture', confirmed=True)
        with self.assertRaises(WorkflowError): self.act('submit_recovery', scenario='recovered')
        with self.assertRaises(WorkflowError): self.act('void', confirmed=True)

    def test_void_without_recovery_and_capture_after_void_blocked(self):
        self.authorize()
        with self.assertRaises(WorkflowError): self.act('void', confirmed=False)
        result = self.act('void', confirmed=True)
        self.assertEqual(result['payment']['status'], 'voided')
        self.assertEqual(result['repair'], 'unverified')
        self.assertEqual(result, self.act('void', confirmed=True))
        with self.assertRaises(WorkflowError): self.act('capture', confirmed=True)

    def test_idempotent_authorize_capture_survive_restart(self):
        result = self.authorize()
        self.assertEqual(result, self.act('authorize'))
        self.recover()
        result = self.act('capture', confirmed=True)
        self.flow = Workflow(self.db, copy.deepcopy(CASES), self.adapter)
        self.assertEqual(result, self.act('capture', confirmed=True))
        self.assertEqual(result, self.act('create_order'))
        self.assertEqual([action for action, _ in self.adapter.calls], ['create', 'authorize', 'capture'])

    def test_create_timeout_locks_review_and_uses_same_id_after_restart(self):
        self.approve()
        self.adapter.errors['create'] = True
        with self.assertRaises(PaymentError): self.act('create_order')
        state = self.flow.snapshot('B')
        self.assertIsNone(state['payment'])
        self.assertEqual(state['pending_operation']['action'], 'create_order')
        with self.assertRaises(WorkflowError): self.review()
        with self.assertRaises(WorkflowError): self.act('rehearse')
        key = self.adapter.calls[-1][1][-1]
        self.flow = Workflow(self.db, copy.deepcopy(CASES), self.adapter)
        self.adapter.errors.clear()
        self.act('create_order')
        self.assertEqual(key, self.adapter.calls[-1][1][-1])

    def test_capture_timeout_blocks_void_and_evidence_change_and_can_reconcile(self):
        self.authorize()
        self.recover()
        self.adapter.errors['capture'] = True
        for _ in range(2):
            with self.assertRaises(PaymentError): self.act('capture', confirmed=True)
        capture_calls = [args for action, args in self.adapter.calls if action == 'capture']
        self.assertEqual(capture_calls[0][-1], capture_calls[1][-1])
        with self.assertRaises(WorkflowError): self.act('void', confirmed=True)
        with self.assertRaises(WorkflowError): self.act('submit_recovery', scenario='still_faulty')
        self.adapter.remote.update(status='completed', capture_id='CAPTURE123')
        result = self.act('reconcile')
        self.assertIsNone(result['pending_operation'])
        self.assertEqual(result['payment']['status'], 'completed')

    def test_reconcile_authorized_does_not_clear_uncertain_capture(self):
        self.authorize()
        self.recover()
        self.adapter.errors['capture'] = True
        with self.assertRaises(PaymentError): self.act('capture', confirmed=True)
        result = self.act('reconcile')
        self.assertEqual(result['pending_operation']['action'], 'capture')

    def test_provider_pending_is_not_completed_and_blocks_void(self):
        self.authorize()
        self.recover()
        with patch.object(self.adapter, 'capture_authorization', return_value=dict(self.adapter.remote, status='pending', capture_id='CAPTURE123')):
            result = self.act('capture', confirmed=True)
        self.assertEqual(result['payment']['status'], 'pending')
        self.assertEqual(result['pending_operation']['action'], 'capture')
        with self.assertRaises(WorkflowError): self.act('void', confirmed=True)

    def test_expired_retry_window_never_resubmits_uncertain_request(self):
        self.approve()
        self.adapter.errors['create'] = True
        with self.assertRaises(PaymentError): self.act('create_order')
        state = self.flow._get('B')
        state['pending_operation']['started_at'] = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
        self.flow._save('B', state)
        self.adapter.errors.clear()
        with self.assertRaises(WorkflowError): self.act('create_order')
        self.assertEqual(len(self.adapter.calls), 1)

    def test_legacy_record_preserved_but_read_only(self):
        state = self.flow._get('B')
        state['payment'] = {'mode': 'local_rehearsal', 'status': 'rehearsed', 'record_id': 'OLD'}
        self.flow._save('B', state)
        self.flow = Workflow(self.db, CASES, self.adapter)
        self.assertEqual(self.flow.snapshot('B')['payment']['record_id'], 'OLD')
        with self.assertRaises(WorkflowError): self.act('capture', confirmed=True)

    def test_warranty_draft_cannot_be_treated_as_completed_repair(self):
        self.act('review', decision='warranty', note=NOTE, confirmed=True)
        with self.assertRaises(WorkflowError): self.act('submit_recovery', scenario='recovered')

    def test_unconfigured_adapter_never_calls_network(self):
        self.approve()
        self.flow.paypal = PayPal('http://127.0.0.1:8766')
        self.flow.paypal.client_id = self.flow.paypal.secret = ''
        with patch('urllib.request.urlopen') as network:
            with self.assertRaises(PaymentError): self.act('create_order')
            network.assert_not_called()
        self.assertIsNone(self.flow.snapshot('B')['payment'])


if __name__ == '__main__':
    unittest.main()
