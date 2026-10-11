"""AI evidence binding and report tests. Only temporary SQLite and fake payments."""
from copy import deepcopy
from pathlib import Path
import tempfile
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from workflow import Workflow, WorkflowError
from case_report import render_case_report

NOTE = 'I inspected the original observations and the reported anomaly.'
ACCEPT = 'I reviewed the independent synthetic recovery observations.'
AI = {'status':'ready', 'model':{'id':'triage-test-v1', 'sha256':'a'*64, 'training_data':'synthetic'},
      'inputs_sha256':'b'*64, 'evidence_sha256':'c'*64, 'summary_code':'stuck', 'pattern':'stuck',
      'signals':[{'code':'flat_duration_hours','value':24,'unit':'hours','device_id':'sensor-A',
                  'source_range':{'start':'2026-10-08T00:00:00Z','end':'2026-10-08T23:00:00Z'}}],
      'devices':[{'id':'sensor-A','pattern':'stuck','status':'ready'}]}
CASE = {'id':'B','title':'Synthetic case','provenance':'synthetic',
        'analysis':{'category':'reading_anomaly','summary':'Inspection lead only'},'series':[], 'ai':AI}

class FakePayPal:
    configured = True
    def __init__(self): self.calls=[]; self.fail_create=False
    def create(self, case_id, amount, request_id):
        self.calls.append(('create',case_id,amount,request_id))
        if self.fail_create:
            self.fail_create=False
            raise TimeoutError('Controlled unknown outcome')
        return {'status':'awaiting_buyer','order_id':'TEST-ORDER'}
    def authorize(self, order_id, case_id, amount, request_id):
        self.calls.append(('authorize',order_id,case_id,amount,request_id))
        return {'status':'authorized','authorization_id':'TEST-AUTH'}
    def void_authorization(self, order_id, authorization_id, case_id, amount, request_id):
        self.calls.append(('void',order_id,authorization_id,case_id,amount,request_id))
        return {'status':'voided'}
    def reconcile(self, *args):
        self.calls.append(('reconcile',*args))
        return {'status':'voided'}
    def capture_authorization(self, *args, **kwargs):
        raise AssertionError('These tests never invoke provider capture')

class AIWorkflowTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='fieldfix-ai-workflow-')
        self.addCleanup(temp.cleanup)
        self.folder=Path(temp.name); self.serial=0
        self.flow,self.paypal=self.make_flow()
    def make_flow(self, case=None):
        self.serial+=1; adapter=FakePayPal()
        return Workflow(self.folder/('case-'+str(self.serial)+'.sqlite'),[deepcopy(CASE if case is None else case)],adapter),adapter
    def review(self, flow=None, decision='replace', **extra):
        return (flow or self.flow).act('B','review',dict(decision=decision,note=NOTE,confirmed=True,**extra))
    def approve(self, flow=None): return (flow or self.flow).act('B','approve',{'confirmed':True})
    def test_missing_unavailable_and_insufficient_ai_block_replacement_and_warranty(self):
        for evidence in (None, {}, {'status':'unavailable'}, {'status':'insufficient'}):
            for decision in ('replace','warranty'):
                with self.subTest(evidence=evidence,decision=decision):
                    case=deepcopy(CASE); case['ai']=evidence
                    flow,paypal=self.make_flow(case); before=flow.snapshot('B')
                    with self.assertRaises(WorkflowError): self.review(flow,decision)
                    self.assertEqual(flow.snapshot('B'),before)
                    self.assertEqual(paypal.calls,[])
    def test_all_three_hashes_must_be_64_hex_and_model_must_be_identified(self):
        paths=(('model','sha256'),('inputs_sha256',),('evidence_sha256',))
        for path in paths:
            for bad in ('a'*63,'x'*64,None,64):
                with self.subTest(path=path,bad=bad):
                    case=deepcopy(CASE); parent=case['ai']
                    for key in path[:-1]: parent=parent[key]
                    parent[path[-1]]=bad
                    flow,_=self.make_flow(case)
                    with self.assertRaises(WorkflowError): self.review(flow)
        case=deepcopy(CASE);case['ai']['model']['id']=''
        flow,_=self.make_flow(case)
        with self.assertRaises(WorkflowError):self.review(flow)
    def test_observation_review_remains_possible_without_model_and_never_approves_payment(self):
        self.flow.cases['B']['ai']={'status':'unavailable'}
        state=self.review(decision='observe')
        self.assertEqual(state['ai_review'],{'status':'unavailable'})
        self.assertFalse(state['approved']);self.assertIsNone(state['payment'])
        with self.assertRaises(WorkflowError):self.approve()
        self.assertEqual(self.paypal.calls,[])
    def test_client_body_cannot_replace_trusted_evidence_or_its_identity(self):
        injected=deepcopy(AI);injected['model']['id']='CLIENT-FORGERY'
        state=self.review(ai=injected,ai_review=injected,inputs_sha256='f'*64)
        self.assertEqual(state['ai_review'],AI)
        self.flow.cases['B']['ai']['inputs_sha256']='d'*64
        with self.assertRaises(WorkflowError):
            self.flow.act('B','approve',{'confirmed':True,'ai':AI,'ai_review':AI})
        self.flow.cases['B']['ai']={'status':'unavailable'}
        with self.assertRaises(WorkflowError):self.review(ai=AI)
        self.assertEqual(self.paypal.calls,[])
    def test_model_input_and_output_changes_require_new_review_before_approval(self):
        for path in (('model','id'),('model','sha256'),('inputs_sha256',),('evidence_sha256',)):
            with self.subTest(path=path):
                flow,paypal=self.make_flow();original=self.review(flow)
                target=flow.cases['B']['ai']
                for key in path[:-1]:target=target[key]
                target[path[-1]]='new-model' if path[-1]=='id' else 'd'*64
                with self.assertRaises(WorkflowError):self.approve(flow)
                self.assertEqual(flow.snapshot('B'),original)
                rereviewed=self.review(flow)
                approved=self.approve(flow)
                self.assertTrue(approved['approved'])
                self.assertEqual(approved['ai_review'],rereviewed['ai_review'])
                self.assertEqual(paypal.calls,[])
    def test_new_orders_and_rehearsals_recheck_binding_after_quote_approval(self):
        for action in ('rehearse','create_order'):
            for changed in ('input','unavailable'):
                with self.subTest(action=action,changed=changed):
                    flow,paypal=self.make_flow();self.review(flow);approved=self.approve(flow)
                    if changed=='input':flow.cases['B']['ai']['inputs_sha256']='d'*64
                    else:flow.cases['B']['ai']['status']='unavailable'
                    with self.assertRaises(WorkflowError):flow.act('B',action,{'ai':AI})
                    self.assertEqual(flow.snapshot('B'),approved)
                    self.assertEqual(paypal.calls,[])
    def test_legacy_review_is_not_retroactively_bound_to_current_model(self):
        case=deepcopy(CASE);case.pop('ai')
        flow,paypal=self.make_flow(case);self.review(flow)
        flow.cases['B']['ai']=deepcopy(AI)
        with self.assertRaises(WorkflowError):self.approve(flow)
        self.assertIsNone(flow.snapshot('B')['ai_review'])
        self.review(flow);self.assertTrue(self.approve(flow)['approved'])
        self.assertEqual(paypal.calls,[])
    def test_ai_cannot_bypass_original_category_or_human_and_recovery_gates(self):
        self.assertIsNone(self.flow.snapshot('B')['review'])
        self.assertFalse(self.flow.snapshot('B')['approved'])
        self.flow.cases['B']['analysis']['category']='shared_connection'
        with self.assertRaises(WorkflowError):self.review()
        self.flow.cases['B']['analysis']['category']='reading_anomaly'
        self.review();self.approve();self.flow.act('B','rehearse',{})
        with self.assertRaises(WorkflowError):self.flow.act('B','capture',{'confirmed':True})
        state=self.flow.act('B','submit_recovery',{'scenario':'recovered'})
        self.assertEqual(state['repair'],'unverified');self.assertEqual(state['payment']['status'],'authorized')
        with self.assertRaises(WorkflowError):self.flow.act('B','capture',{'confirmed':True})
        self.flow.act('B','verify_repair',{'note':ACCEPT,'confirmed':True})
        with self.assertRaises(WorkflowError):self.flow.act('B','capture',{'confirmed':False})
        self.assertEqual(self.paypal.calls,[])
    def test_repeated_confirmations_and_existing_local_settlement_are_idempotent(self):
        self.review();approved=self.approve();self.assertEqual(self.approve(),approved)
        authorized=self.flow.act('B','rehearse',{})
        self.flow.cases['B']['ai']={'status':'unavailable'}
        self.assertEqual(self.flow.act('B','rehearse',{}),authorized)
        self.flow.act('B','submit_recovery',{'scenario':'recovered'})
        accepted=self.flow.act('B','verify_repair',{'note':ACCEPT,'confirmed':True})
        self.assertEqual(self.flow.act('B','verify_repair',{'note':ACCEPT,'confirmed':True}),accepted)
        paid=self.flow.act('B','capture',{'confirmed':True})
        self.assertEqual(self.flow.act('B','capture',{'confirmed':True}),paid)
        self.assertEqual(paid['payment']['mode'],'local_rehearsal')
        self.assertEqual(paid['ai_review'],AI)
        self.assertEqual(self.paypal.calls,[])
    def test_existing_sandbox_authorization_can_be_voided_and_reconciled_when_ai_fails(self):
        self.review();self.approve();self.flow.act('B','create_order',{})
        self.flow.act('B','authorize',{})
        self.flow.cases['B']['ai']={'status':'unavailable'}
        voided=self.flow.act('B','void',{'confirmed':True})
        self.assertEqual(self.flow.act('B','void',{'confirmed':True}),voided)
        reconciled=self.flow.act('B','reconcile',{})
        self.assertEqual(reconciled['payment']['status'],'voided')
        self.assertEqual([c[0] for c in self.paypal.calls],['create','authorize','void','reconcile'])
        self.assertEqual(reconciled['repair'],'unverified')
    def test_pending_create_retries_original_request_instead_of_stranding_unknown_payment(self):
        self.review();self.approve();self.paypal.fail_create=True
        with self.assertRaises(TimeoutError):self.flow.act('B','create_order',{})
        self.assertEqual(self.flow.snapshot('B')['pending_operation']['action'],'create_order')
        self.flow.cases['B']['ai']={'status':'unavailable'}
        state=self.flow.act('B','create_order',{})
        self.assertEqual(state['payment']['status'],'awaiting_buyer')
        self.assertEqual(self.paypal.calls[0],self.paypal.calls[1])
        self.assertIsNone(state['pending_operation'])
    def test_old_authorization_with_no_ai_binding_remains_recoverable_without_fabrication(self):
        case=deepcopy(CASE);case.pop('ai')
        flow,_=self.make_flow(case);self.review(flow);self.approve(flow);flow.act('B','rehearse',{})
        flow.cases['B']['ai']={'status':'unavailable'}
        voided=flow.act('B','void',{'confirmed':True})
        self.assertEqual(voided['payment']['status'],'voided')
        self.assertIsNone(voided['ai_review'])
        self.assertIsNone(voided['evidence_history'][0]['after']['ai_review'])
    def test_versions_deep_copy_full_model_signals_and_case_evidence(self):
        first=self.review()
        self.flow.cases['B']['ai']['signals'][0]['value']=99
        self.flow.cases['B']['ai']['devices'][0]['pattern']='normal'
        self.flow.cases['B']['ai']['evidence_sha256']='d'*64
        second=self.review()
        old=second['evidence_history'][0]
        self.assertEqual(old['after']['ai_review'],AI)
        self.assertEqual(old['case_evidence']['ai'],AI)
        self.assertEqual(second['evidence_history'][1]['before']['ai_review'],AI)
        self.assertEqual(first['ai_review'],AI)
        self.assertEqual(second['ai_review']['signals'][0]['value'],99)
        second['ai_review']['signals'][0]['value']=0
        self.assertEqual(self.flow.snapshot('B')['ai_review']['signals'][0]['value'],99)

class AIReportTests(unittest.TestCase):
    def test_bound_inference_is_brief_bilingual_and_sources_keep_original_ranges(self):
        state={'review':{'decision':'replace','note':'原文人工检查记录保留。'},'ai_review':deepcopy(AI),'repair':'unverified'}
        for lang in ('en','zh-CN'):
            report=render_case_report(CASE,state,lang)
            for value in ('triage-test-v1','a'*64,'b'*64,'c'*64,'sensor-A','2026-10-08T00:00:00Z','2026-10-08T23:00:00Z','原文人工检查记录保留。'):
                self.assertIn(value,report)
            self.assertIn('<details class="ai-details">',report)
        report=render_case_report(CASE,state)
        self.assertIn('recorded local model inference completed',report)
        self.assertIn('training data was synthetic',report)
        self.assertIn('Unchanged-reading duration',report)
        self.assertIn('Payment does not prove repair.',report)
        self.assertNotIn('Case analysis uses a demonstration statistical baseline.',report)
    def test_current_ai_does_not_retroactively_bind_legacy_decision(self):
        state={'review':{'decision':'replace','note':NOTE},'repair':'unverified'}
        report=render_case_report(CASE,state)
        self.assertIn('No AI evidence was bound to this human decision.',report)
        self.assertIn('Current AI result',report)
        self.assertNotIn('AI evidence recorded with this human review',report)
        old=deepcopy(CASE);old.pop('ai')
        legacy=render_case_report(old,state)
        self.assertIn('No AI evidence was bound',legacy)
        self.assertNotIn('local model inference completed',legacy)
    def test_changed_current_result_preserves_reviewed_pattern_and_old_hash(self):
        current=deepcopy(CASE);current['ai']={'status':'unavailable'}
        report=render_case_report(current,{'ai_review':AI,'repair':'unverified'})
        self.assertIn('current AI result differs',report)
        self.assertIn('Readings stayed unusually constant',report)
        self.assertIn('Model unavailable',report)
        self.assertIn('c'*64,report)
    def test_signal_fields_are_escaped_and_unknown_private_fields_are_not_exported(self):
        ai=deepcopy(AI)
        ai['signals'].append({'code':'<script>bad</script>','value':1,'unit':'unknown-unit','device_id':'<img src=x onerror=bad()>','source_range':{'start':'<svg onload=bad()>','end':'C:\\Users\\Private\\test.csv'},'secret':'SIGNAL-SECRET'})
        ai['client_secret']='MODEL-SECRET';ai['devices'].append({'private_path':'C:\\Users\\Hidden\\raw.csv'})
        report=render_case_report(dict(CASE,ai=ai),{'ai_review':ai})
        self.assertNotIn('<script>',report);self.assertNotIn('<img ',report);self.assertNotIn('<svg ',report)
        self.assertIn('&lt;script&gt;',report)
        for hidden in ('MODEL-SECRET','SIGNAL-SECRET','Private','Hidden'):self.assertNotIn(hidden,report)
    def test_unavailable_inference_never_claims_model_success(self):
        case=deepcopy(CASE);case['ai']={'status':'insufficient'}
        report=render_case_report(case,{'ai_review':{'status':'insufficient'}})
        self.assertIn('Inputs insufficient',report)
        self.assertIn('A usable model result is not recorded',report)
        self.assertNotIn('local model inference completed',report)

if __name__=='__main__':unittest.main()