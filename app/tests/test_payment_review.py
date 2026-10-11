"""Independent payment recovery regressions; no network or real credentials."""
import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paypal import PayPal, PaymentError
from workflow import Workflow


class PaymentReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fieldfix-payment-review-")
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "review.sqlite"
        self.cases = [{"id": "REVIEW1", "analysis": {"category": "reading_anomaly"}}]
        self.adapter = PayPal("http://127.0.0.1:8766")
        self.token = patch.object(self.adapter, "_token", return_value="unit-test-token")
        self.token.start()
        self.addCleanup(self.token.stop)
        self.flow = Workflow(self.db, self.cases, self.adapter)
        self.flow.act("REVIEW1", "review", {
            "decision": "replace", "note": "Synthetic independent field inspection.", "confirmed": True})
        self.flow.act("REVIEW1", "approve", {"confirmed": True})
        state = self.flow._get("REVIEW1")
        state["payment"] = {"mode": "paypal_sandbox", "intent": "AUTHORIZE", "status": "authorized",
                            "order_id": "ORDERREVIEW1", "authorization_id": "AUTHREVIEW1",
                            "amount": "25.00", "currency": "NZD"}
        self.flow._save("REVIEW1", state)
        self.flow.act("REVIEW1", "submit_recovery", {"scenario": "recovered"})
        self.flow.act("REVIEW1", "verify_repair", {
            "note": "Synthetic recovery inspected independently.", "confirmed": True})
        self.auth = {"id": "AUTHREVIEW1", "status": "CREATED",
                     "amount": {"value": "25.00", "currency_code": "NZD"},
                     "create_time": datetime.now(timezone.utc).isoformat(),
                     "expiration_time": (datetime.now(timezone.utc) + timedelta(days=29)).isoformat()}
        self.capture_gets = 0
        self.capture_get_failure = False
        self.mutations = []

    def provider(self, path, payload=None, token=None, request_id=None, oauth=False):
        if payload is not None:
            self.mutations.append((path, copy.deepcopy(payload), request_id))
        if path == "/v2/checkout/orders/ORDERREVIEW1":
            # Deliberately never embeds captures: recovery must use the durable ID.
            return {"id": "ORDERREVIEW1", "intent": "AUTHORIZE", "status": "COMPLETED",
                    "purchase_units": [{"reference_id": "REVIEW1", "custom_id": "REVIEW1",
                        "amount": {"value": "25.00", "currency_code": "NZD"},
                        "payments": {"authorizations": [copy.deepcopy(self.auth)]}}]}
        if path == "/v2/payments/authorizations/AUTHREVIEW1":
            return copy.deepcopy(self.auth)
        if path == "/v2/payments/authorizations/AUTHREVIEW1/capture":
            self.auth["status"] = "CAPTURED"
            return {"id": "CAPREVIEW1"}
        if path == "/v2/payments/captures/CAPREVIEW1":
            self.capture_gets += 1
            if self.capture_get_failure:
                raise PaymentError("Controlled GET timeout after capture POST succeeded")
            return {"id": "CAPREVIEW1", "status": "COMPLETED",
                    "amount": {"value": "25.00", "currency_code": "NZD"},
                    "supplementary_data": {"related_ids": {
                        "order_id": "ORDERREVIEW1", "authorization_id": "AUTHREVIEW1"}}}
        if path == "/v2/payments/authorizations/AUTHREVIEW1/void":
            self.auth["status"] = "VOIDED"
            return {}
        self.fail("Unexpected provider request: " + path)

    def test_capture_id_survives_get_timeout_and_restart_without_another_post(self):
        original = self.flow.snapshot("REVIEW1")
        self.capture_get_failure = True
        with patch.object(self.adapter, "_json", side_effect=self.provider):
            with self.assertRaises(PaymentError):
                self.flow.act("REVIEW1", "capture", {"confirmed": True})
        uncertain = self.flow.snapshot("REVIEW1")
        self.assertEqual(uncertain["payment"]["capture_id"], "CAPREVIEW1")
        self.assertEqual(uncertain["payment"]["status"], "pending")
        self.assertEqual(uncertain["pending_operation"]["action"], "capture")
        self.assertEqual(len(self.mutations), 1)
        self.capture_get_failure = False
        restarted = Workflow(self.db, self.cases, self.adapter)
        with patch.object(self.adapter, "_json", side_effect=self.provider):
            recovered = restarted.act("REVIEW1", "reconcile", {})
        self.assertEqual(recovered["payment"]["status"], "completed")
        self.assertEqual(recovered["payment"]["capture_id"], "CAPREVIEW1")
        self.assertIsNone(recovered["pending_operation"])
        self.assertEqual(len(self.mutations), 1, "Recovery must not POST a second payment")
        self.assertEqual(self.capture_gets, 2)
        self.assertEqual(recovered["quote"], original["quote"])
        self.assertEqual(recovered["recovery"], original["recovery"])
        self.assertEqual(recovered["history"][:len(original["history"])], original["history"])

    def test_first_capture_rejected_before_post_does_not_lock_out_void(self):
        self.auth["create_time"] = (datetime.now(timezone.utc) - timedelta(days=4)).isoformat()
        with patch.object(self.adapter, "_json", side_effect=self.provider):
            with self.assertRaises(PaymentError):
                self.flow.act("REVIEW1", "capture", {"confirmed": True})
            self.assertEqual(self.mutations, [], "Cutoff rejection happens before any payment POST")
            self.assertIsNone(self.flow.snapshot("REVIEW1")["pending_operation"])
            result = self.flow.act("REVIEW1", "void", {"confirmed": True})
        self.assertEqual(result["payment"]["status"], "voided")
        self.assertEqual([item[0] for item in self.mutations],
                         ["/v2/payments/authorizations/AUTHREVIEW1/void"])

    def test_preflight_rejection_during_retry_preserves_older_uncertain_capture(self):
        state = self.flow._get("REVIEW1")
        pending = {"action": "capture", "started_at": datetime.now(timezone.utc).isoformat()}
        state["pending_operation"] = copy.deepcopy(pending)
        self.flow._save("REVIEW1", state)
        self.auth["create_time"] = (datetime.now(timezone.utc) - timedelta(days=4)).isoformat()
        with patch.object(self.adapter, "_json", side_effect=self.provider):
            with self.assertRaises(PaymentError):
                self.flow.act("REVIEW1", "capture", {"confirmed": True})
        self.assertEqual(self.mutations, [])
        self.assertEqual(self.flow.snapshot("REVIEW1")["pending_operation"], pending)


if __name__ == "__main__":
    unittest.main()
