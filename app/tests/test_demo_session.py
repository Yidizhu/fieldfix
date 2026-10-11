"""Rehearsal isolation and full approval/recovery lifecycle without any network."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from demo_session import OfflinePayPal, new_demo_database
from analysis_engine import get_cases
from paypal import PaymentPreflightError
from workflow import Workflow, WorkflowError


class DemoSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.adapter = OfflinePayPal("http://127.0.0.1:8767")
        self.db = new_demo_database(self.root)
        self.workflow = Workflow(self.db, get_cases(), self.adapter)

    def authorize(self):
        self.workflow.act("FF-102", "review", {"decision":"replace", "note":"Synthetic inspection confirms a service visit is needed.", "confirmed":True})
        self.workflow.act("FF-102", "approve", {"confirmed":True})
        return self.workflow.act("FF-102", "rehearse", {})

    def test_rehearsal_cannot_read_credentials_or_make_provider_request(self):
        with patch.dict(os.environ, {"PAYPAL_SANDBOX_CLIENT_ID":"must-not-load", "PAYPAL_SANDBOX_CLIENT_SECRET":"must-not-load"}), patch("urllib.request.urlopen", side_effect=AssertionError("Network must stay off")):
            adapter = OfflinePayPal("http://127.0.0.1:8767")
            self.assertFalse(adapter.configured)
            self.assertEqual(adapter.secret, "")
            with self.assertRaises(PaymentPreflightError):adapter.create("FF-102", "25.00", "fake-request-id")
            with self.assertRaises(PaymentPreflightError):adapter._json("/anything")

    def test_new_session_does_not_reuse_or_modify_previous_cases(self):
        old = self.authorize()
        before = self.db.read_bytes()
        other = new_demo_database(self.root)
        self.assertNotEqual(self.db, other)
        fresh = Workflow(other, get_cases(), self.adapter)
        self.assertIsNone(fresh.snapshot("FF-102")["payment"])
        self.assertEqual(self.db.read_bytes(), before)
        self.assertEqual(Workflow(self.db, get_cases(), self.adapter).snapshot("FF-102")["payment"], old["payment"])

    def test_failed_or_missing_evidence_blocks_capture_then_recovery_allows_one(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("No network in rehearsal")):
            self.authorize()
            for scenario in ("still_faulty", "insufficient"):
                self.workflow.act("FF-102", "submit_recovery", {"scenario":scenario})
                with self.assertRaises(WorkflowError):
                    self.workflow.act("FF-102", "verify_repair", {"note":"Checked the synthetic recovery records.", "confirmed":True})
                with self.assertRaises(WorkflowError):self.workflow.act("FF-102", "capture", {"confirmed":True})
            self.workflow.act("FF-102", "submit_recovery", {"scenario":"recovered"})
            self.workflow.act("FF-102", "verify_repair", {"note":"Checked the synthetic recovery records.", "confirmed":True})
            result = self.workflow.act("FF-102", "capture", {"confirmed":True})
            self.assertEqual(result["payment"]["status"], "completed")
            self.assertEqual(result["payment"]["mode"], "local_rehearsal")
            self.assertEqual(self.workflow.act("FF-102", "capture", {"confirmed":True}), result)
            restarted = Workflow(self.db, get_cases(), self.adapter)
            self.assertEqual(restarted.snapshot("FF-102")["payment"], result["payment"])

    def test_void_is_a_separate_valid_end_without_repair_or_capture(self):
        self.authorize()
        result = self.workflow.act("FF-102", "void", {"confirmed":True})
        self.assertEqual(result["payment"]["status"], "voided")
        self.assertNotEqual(result["repair"], "verified_demo")
        with self.assertRaises(WorkflowError):self.workflow.act("FF-102", "capture", {"confirmed":True})


if __name__ == "__main__":unittest.main()
