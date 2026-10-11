"""Business-risk tests: temporary SQLite, fake adapters, and no network calls."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

APP = Path(__file__).resolve().parents[1]
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))
from paypal import PayPal, PaymentError, verify_capture
from workflow import Workflow, WorkflowError

CASES = [
    {"id": "B", "analysis": {"category": "reading_anomaly"}},
    {"id": "A", "analysis": {"category": "shared_outage"}},
    {"id": "C", "analysis": {"category": "normal"}},
]
NOTE = "Simulated on-site inspection confirms the selected action."


def order_response(status="COMPLETED", order_id="ORDER123", case_id="B"):
    unit = {
        "reference_id": case_id, "custom_id": case_id,
        "amount": {"currency_code": "NZD", "value": "25.00"},
    }
    if status == "COMPLETED":
        unit["payments"] = {"captures": [{
            "id": "CAPTURE123", "status": "COMPLETED",
            "amount": {"currency_code": "NZD", "value": "25.00"},
        }]}
    return {"id": order_id, "status": status, "purchase_units": [unit]}


class PayPalVerificationTests(unittest.TestCase):
    def adapter(self):
        adapter = PayPal("http://127.0.0.1:8765")
        adapter.client_id, adapter.secret = "unit-test-id", "unit-test-secret"
        return adapter

    def test_completed_payment_must_match_order_case_amount_currency_and_count(self):
        changes = {
            "order": lambda d: d.update(id="OTHERORDER"),
            "order_status": lambda d: d.update(status="APPROVED"),
            "case_reference": lambda d: d["purchase_units"][0].update(reference_id="A"),
            "case_custom": lambda d: d["purchase_units"][0].update(custom_id="A"),
            "amount": lambda d: d["purchase_units"][0]["payments"]["captures"][0]["amount"].update(value="25.01"),
            "currency": lambda d: d["purchase_units"][0]["payments"]["captures"][0]["amount"].update(currency_code="USD"),
            "capture_status": lambda d: d["purchase_units"][0]["payments"]["captures"][0].update(status="PENDING"),
            "missing_capture": lambda d: d["purchase_units"][0].update(payments={"captures": []}),
            "multiple_units": lambda d: d["purchase_units"].append(copy.deepcopy(d["purchase_units"][0])),
            "multiple_captures": lambda d: d["purchase_units"][0]["payments"]["captures"].append(copy.deepcopy(d["purchase_units"][0]["payments"]["captures"][0])),
        }
        for label, change in changes.items():
            with self.subTest(mismatch=label):
                data = order_response()
                change(data)
                with self.assertRaises(PaymentError):
                    verify_capture(data, "ORDER123", "B", "25.00")

    def test_cancelled_or_unapproved_order_never_sends_capture(self):
        for status in ("CREATED", "PAYER_ACTION_REQUIRED", "VOIDED"):
            with self.subTest(status=status):
                adapter = self.adapter()
                with patch.object(adapter, "_token", return_value="fake-token"), patch.object(adapter, "_json", return_value=order_response(status)) as provider:
                    with self.assertRaises(PaymentError):
                        adapter.capture("ORDER123", "B", "25.00", "capture-key")
                    self.assertEqual(provider.call_count, 1)
                    self.assertEqual(provider.call_args.args[0], "/v2/checkout/orders/ORDER123")

    def test_approved_order_is_verified_before_any_capture_side_effect(self):
        changes = {
            "order": lambda d: d.update(id="OTHERORDER"),
            "case_reference": lambda d: d["purchase_units"][0].update(reference_id="A"),
            "case_custom": lambda d: d["purchase_units"][0].update(custom_id="A"),
            "amount": lambda d: d["purchase_units"][0]["amount"].update(value="250.00"),
            "currency": lambda d: d["purchase_units"][0]["amount"].update(currency_code="USD"),
            "multiple_units": lambda d: d["purchase_units"].append(copy.deepcopy(d["purchase_units"][0])),
        }
        for label, change in changes.items():
            with self.subTest(mismatch=label):
                before = order_response("APPROVED")
                change(before)
                adapter = self.adapter()
                with patch.object(adapter, "_token", return_value="fake-token"), patch.object(adapter, "_json", side_effect=[before, order_response()]) as provider:
                    with self.assertRaises(PaymentError):
                        adapter.capture("ORDER123", "B", "25.00", "capture-key")
                    self.assertEqual(provider.call_count, 1, "Mismatched approved order must be rejected BEFORE the capture POST")

    def test_completed_remote_order_is_verified_without_recapturing(self):
        adapter = self.adapter()
        with patch.object(adapter, "_token", return_value="fake-token"), patch.object(adapter, "_json", return_value=order_response()) as provider:
            result = adapter.capture("ORDER123", "B", "25.00", "capture-key")
        self.assertEqual(provider.call_count, 1)
        self.assertEqual(result["capture_id"], "CAPTURE123")

    def test_valid_approved_order_can_be_captured_once(self):
        adapter = self.adapter()
        responses = [
            order_response("APPROVED"),
            {"id": "ORDER123", "status": "COMPLETED"},  # PayPal may return a minimal capture response.
            order_response(),
        ]
        with patch.object(adapter, "_token", return_value="fake-token"), patch.object(adapter, "_json", side_effect=responses) as provider:
            result = adapter.capture("ORDER123", "B", "25.00", "capture-key")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["capture_id"], "CAPTURE123")
        self.assertEqual(provider.call_count, 3)
        calls = provider.call_args_list
        self.assertEqual([call.args[0] for call in calls], [
            "/v2/checkout/orders/ORDER123",
            "/v2/checkout/orders/ORDER123/capture",
            "/v2/checkout/orders/ORDER123",
        ])
        self.assertEqual(calls[1].args, ("/v2/checkout/orders/ORDER123/capture", {}, "fake-token", "capture-key"))
        self.assertEqual(calls[-1].args, ("/v2/checkout/orders/ORDER123",))
        self.assertEqual(calls[-1].kwargs, {"token": "fake-token"})

    def test_malformed_capture_amount_is_a_payment_error(self):
        for value in ("not-money", "NaN", "Infinity", None):
            with self.subTest(value=value):
                data = order_response()
                data["purchase_units"][0]["payments"]["captures"][0]["amount"]["value"] = value
                with self.assertRaises(PaymentError):
                    verify_capture(data, "ORDER123", "B", "25.00")


if __name__ == "__main__":
    unittest.main()
