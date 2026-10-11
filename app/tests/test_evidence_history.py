"""Evidence audit tests: isolated SQLite and an adapter that forbids all calls."""
import copy
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workflow import Workflow, WorkflowError

CASE={'id':'B','provenance':'synthetic','analysis':{'category':'reading_anomaly','summary':'Demo baseline evidence'},'series':[{'id':'sensor','points':[{'t':'2026-10-08T00:00:00Z','value':30.0}]}]}
NOTE='Original inspection note for the synthetic demonstration.'
ACCEPT='Original acceptance note after reviewing all synthetic evidence.'
class NoNetwork:
    configured=False
    def __getattr__(self,name):
        raise AssertionError('No payment adapter call is permitted: '+name)

class EvidenceHistoryTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='fieldfix-evidence-')
        self.addCleanup(temp.cleanup)
        self.db=Path(temp.name)/'test.sqlite'
        self.flow=Workflow(self.db,[copy.deepcopy(CASE)],NoNetwork())
    def act(self,action,**body):return self.flow.act('B',action,body)
    def review(self,decision='observe',note=NOTE):return self.act('review',decision=decision,note=note,confirmed=True)
    def test_review_revisions_preserve_decision_note_and_initial_evidence(self):
        first=self.review()
        self.flow.cases['B']['series'][0]['points'][0]['value']=999
        second=self.review('replace',NOTE+' Updated decision.')
        versions=second['evidence_history']
        self.assertEqual(second['evidence_history_origin'],'tracked_from_start')
        self.assertEqual([v['version'] for v in versions],[1,2])
        self.assertEqual(versions[1]['before']['review'],first['review'])
        self.assertEqual(versions[1]['after']['review']['decision'],'replace')
        self.assertEqual(versions[0]['case_evidence']['series'][0]['points'][0]['value'],30)
        self.assertEqual(versions[1]['case_evidence']['series'][0]['points'][0]['value'],999)
        raw=json.dumps(versions[0]['case_evidence'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
        self.assertEqual(versions[0]['case_evidence_sha256'],hashlib.sha256(raw).hexdigest())
        self.assertEqual(versions[0]['after'],first['evidence_history'][0]['after'])
    def test_replacement_evidence_preserves_prior_acceptance_and_invalidates_current(self):
        self.review()
        self.act('submit_recovery',scenario='recovered')
        accepted=self.act('verify_repair',note=ACCEPT,confirmed=True)
        after=self.act('submit_recovery',scenario='still_faulty')
        prior=after['evidence_history'][-1]['before']
        self.assertEqual(prior['repair'],'verified_demo')
        self.assertEqual(prior['recovery']['human_review']['note'],ACCEPT)
        self.assertEqual(prior['recovery']['observations'],accepted['recovery']['observations'])
        self.assertEqual(after['repair'],'unverified')
        self.assertNotIn('human_review',after['recovery'])
        self.assertEqual(after['evidence_history'][2]['after']['recovery']['human_review']['note'],ACCEPT)
        with self.assertRaises(WorkflowError):self.act('verify_repair',note=ACCEPT,confirmed=True)
        self.assertEqual(self.flow.snapshot('B'),after)
    def test_repeated_acceptance_does_not_invent_another_decision(self):
        self.review();self.act('submit_recovery',scenario='recovered')
        first=self.act('verify_repair',note=ACCEPT,confirmed=True)
        again=self.act('verify_repair',note=ACCEPT,confirmed=True)
        self.assertEqual(first,again)
        self.assertEqual(len(again['evidence_history']),3)
    def test_rejected_update_changes_neither_history_nor_state(self):
        state=self.flow.snapshot('B')
        with self.assertRaises(WorkflowError):self.act('review',decision='replace',note=NOTE,confirmed=False)
        with self.assertRaises(WorkflowError):self.act('submit_recovery',scenario='recovered')
        with self.assertRaises(WorkflowError):self.act('capture',confirmed=True)
        self.assertEqual(state,self.flow.snapshot('B'))
    def test_legacy_state_is_not_backfilled_and_first_transition_is_honest(self):
        old={'review':{'decision':'observe','note':'Prior original note from an old database.','simulated':True},'approved':False,'payment':None,'repair':'unverified','history':[]}
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('UPDATE cases SET data=? WHERE id=?',(json.dumps(old),'B'))
        flow=Workflow(self.db,[copy.deepcopy(CASE)],NoNetwork())
        initial=flow.snapshot('B')
        self.assertEqual(initial['evidence_history'],[])
        self.assertEqual(initial['evidence_history_origin'],'legacy_unversioned')
        updated=flow.act('B','review',{'decision':'observe','note':NOTE,'confirmed':True})
        entry=updated['evidence_history'][0]
        self.assertEqual(entry['before']['review'],old['review'])
        self.assertEqual(entry['before_origin'],'legacy_state_observed_at_update')
        self.assertNotIn('at',entry['before']['review'])
        self.assertEqual(entry['version'],1)
        self.assertTrue(entry['recorded_at'])
    def test_restart_and_detached_snapshots_preserve_version_content(self):
        first=self.review();self.act('submit_recovery',scenario='insufficient')
        restarted=Workflow(self.db,[copy.deepcopy(CASE)],NoNetwork())
        snapshot=restarted.snapshot('B')
        self.assertEqual(snapshot['evidence_history'][0],first['evidence_history'][0])
        snapshot['evidence_history'][0]['after']['review']['note']='Changed only in caller memory'
        self.assertEqual(restarted.snapshot('B')['evidence_history'][0]['after']['review']['note'],NOTE)
    def test_payment_and_evidence_remain_separate_in_local_rehearsal(self):
        self.review('replace');self.act('approve',confirmed=True);self.act('rehearse')
        self.assertEqual(len(self.flow.snapshot('B')['evidence_history']),1)
        with self.assertRaises(WorkflowError):self.act('capture',confirmed=True)
        self.act('submit_recovery',scenario='recovered')
        accepted=self.act('verify_repair',note=ACCEPT,confirmed=True)
        paid=self.act('capture',confirmed=True)
        self.assertEqual(paid['evidence_history'],accepted['evidence_history'])
        self.assertEqual(paid['payment']['mode'],'local_rehearsal')
        self.assertEqual(paid['payment']['status'],'completed')
    def test_changing_review_preserves_previous_recovery_and_quote(self):
        self.review();self.act('submit_recovery',scenario='recovered')
        self.act('verify_repair',note=ACCEPT,confirmed=True)
        changed=self.review('replace',NOTE+' New plan.')
        self.assertEqual(changed['evidence_history'][-1]['before']['repair'],'verified_demo')
        self.assertIsNone(changed['recovery'])
        self.assertEqual(changed['repair'],'unverified')
        self.act('approve',confirmed=True)
        revised=self.review('observe',NOTE+' Revised plan.')
        self.assertEqual(revised['evidence_history'][-1]['before']['quote']['amount'],'25.00')
        self.assertIsNone(revised['quote'])

if __name__=='__main__':unittest.main()
