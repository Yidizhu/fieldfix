"""Learned evidence actually controls case triage; private research is not used."""
import copy
from pathlib import Path
import re
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from analysis_engine import get_cases
from case_ai import attach_case_ai
from localization import localize_case


class CaseAITests(unittest.TestCase):
    def test_three_cases_have_actual_model_outputs_and_no_payment_authority(self):
        expected=("shared_connection","reading_anomaly","normal")
        for case, category in zip(get_cases(),expected):
            before=copy.deepcopy(case)
            result=attach_case_ai(case)
            self.assertEqual(result["analysis"]["category"],category)
            self.assertEqual(result["ai"]["status"],"ready")
            self.assertTrue(result["ai"]["model_executed"])
            self.assertEqual(result["ai"]["decision_authority"],"human_only")
            self.assertEqual(result["ai"]["model"]["training_data"],"synthetic")
            for key in ("inputs_sha256","evidence_sha256","context_sha256"):
                self.assertRegex(result["ai"][key],r"^[a-f0-9]{64}$")
            self.assertNotIn("payment",result)
            self.assertEqual(case,before)

    def test_readings_not_case_title_or_existing_analysis_control_result(self):
        case=get_cases()[2]
        normal=attach_case_ai(case)
        case["title"]="confirmed faulty buy now"
        case["analysis"]={"category":"reading_anomaly"}
        case["fault_label"]="persistent_shift"
        unchanged=attach_case_ai(case)
        self.assertEqual(unchanged["ai"]["evidence_sha256"],normal["ai"]["evidence_sha256"])
        for point in case["series"][1]["points"][48:]:point["value"]+=9
        shifted=attach_case_ai(case)
        self.assertEqual(shifted["analysis"]["category"],"reading_anomaly")
        self.assertNotEqual(shifted["ai"]["inputs_sha256"],normal["ai"]["inputs_sha256"])

    def test_same_evidence_survives_reruns_and_translation(self):
        case=get_cases()[1]
        first,second=attach_case_ai(case),attach_case_ai(case)
        self.assertEqual(first["ai"]["evidence_sha256"],second["ai"]["evidence_sha256"])
        en=localize_case(first,"en")
        self.assertEqual(en["ai"],first["ai"])
        self.assertFalse(re.search(r"[\u3400-\u9fff]",en["analysis"]["summary"]+en["analysis"]["method"]))

    def test_bad_model_never_falls_back_to_paid_baseline(self):
        case=get_cases()[1]
        with tempfile.TemporaryDirectory() as temp:
            missing=Path(temp)/"missing.json"
            result=attach_case_ai(case,missing)
            self.assertEqual(result["ai"]["status"],"unavailable")
            self.assertEqual(result["analysis"]["category"],"insufficient_data")
            missing.write_text('{"weights":"not a model"}')
            bad=attach_case_ai(case,missing)
            self.assertEqual(bad["ai"]["status"],"unavailable")
            self.assertNotIn(str(missing),str(bad["ai"]))

    def test_one_incomplete_device_prevents_case_wide_all_clear(self):
        case=get_cases()[2]
        case["series"][0]["points"][55]["value"]=None
        result=attach_case_ai(case)
        self.assertEqual(result["ai"]["status"],"insufficient")
        self.assertEqual(result["analysis"]["category"],"insufficient_data")

    def test_shared_connection_comes_from_known_topology_not_ml_root_cause(self):
        case=get_cases()[0]
        for device in case["series"]:device["gateway_id"]="unknown"
        result=attach_case_ai(case)
        self.assertEqual(result["ai"]["summary_code"],"single_dropout")
        self.assertEqual(result["analysis"]["category"],"insufficient_data")
        self.assertTrue(all(d["pattern"]=="dropout" for d in result["ai"]["devices"]))


if __name__=="__main__":unittest.main()
