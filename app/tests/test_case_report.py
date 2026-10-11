"""Report contract, privacy and state-separation tests; no service is contacted."""
import base64
import copy
import hashlib
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from case_report import render_case_report, REPORT_CSS, REPORT_STYLE_CSP, REPORT_CSP

CASE={'id':'FF-102','title':'Synthetic case','provenance':'synthetic','analysis':{'category':'reading_anomaly','summary':'Synthetic baseline evidence','method':'Fixed statistical demonstration baseline','evidence':['Inspect wiring before replacing a device']}}
NOTE='人工原话：已复核接线与接触情况，仍需谨慎判断。'
STATE={'review':{'decision':'replace','note':NOTE,'simulated':True},'approved':True,'quote':{'version':1,'sku':'FF-Soil-01','amount':'25.00','currency':'NZD','seller_role':'monitoring_service_provider','buyer_role':'farm'},'payment':{'mode':'local_rehearsal','intent':'AUTHORIZE','status':'completed','record_id':'DEMO-LOCAL','capture_id':'DEMO-CAPTURE'},'repair':'unverified','recovery':{'source':'synthetic_fixture','scenario':'insufficient','status':'insufficient','sample_count':6},'history':[]}

class ParsedHTML(HTMLParser):
    def __init__(self):super().__init__();self.tags=[];self.text=[]
    def handle_starttag(self,tag,attrs):self.tags.append((tag,dict(attrs)))
    def handle_data(self,data):self.text.append(data)

class CaseReportTests(unittest.TestCase):
    def test_escapes_injected_markup_in_every_rendered_source_layer(self):
        case=copy.deepcopy(CASE);state=copy.deepcopy(STATE)
        attack='<script>alert("x")</script><img src=x onerror=alert(1)> & original'
        case['title']=attack;case['analysis']['summary']=attack
        state['review']['note']=attack;state['quote']['sku']=attack
        state['recovery']['human_review']={'note':attack,'at':'2026-10-11T00:00:00Z'}
        state['evidence_history']=[{'version':1,'recorded_at':'2026-10-11T00:00:00Z','action':'review','before':{},'after':{'review':{'decision':'observe','note':attack},'repair':'unverified'}}]
        report=render_case_report(case,state)
        parsed=ParsedHTML();parsed.feed(report)
        self.assertNotIn('script',[tag for tag,_ in parsed.tags])
        self.assertNotIn('img',[tag for tag,_ in parsed.tags])
        self.assertNotIn('onerror=',str([attrs for _,attrs in parsed.tags]))
        self.assertIn('&lt;script&gt;',report)
        self.assertIn('&lt;/script&gt;',report)
        self.assertIn(attack,''.join(parsed.text))
    def test_local_completion_does_not_prove_recovery_or_acceptance(self):
        report=render_case_report(CASE,STATE)
        for text in ('Charge recorded','Local rehearsal — no PayPal call or funds movement','Insufficient evidence','Not accepted / unverified','Payment does not prove repair.'):
            self.assertIn(text,report)
        self.assertNotIn('Simulated acceptance recorded; no real repair certification',report)
    def test_acceptance_and_authorization_remain_distinct_and_original_note_survives(self):
        state=copy.deepcopy(STATE)
        state['payment'].update(mode='paypal_sandbox',status='authorized',authorization_id='TEST-AUTH')
        state['repair']='verified_demo'
        state['recovery'].update(status='pass',human_review={'note':NOTE,'at':'2026-10-11T00:00:00Z','simulated':True})
        for lang in ('en','zh-CN'):
            report=render_case_report(CASE,state,lang)
            self.assertIn(NOTE,report)
            self.assertIn('TEST-AUTH',report)
        self.assertIn('Authorized; not charged',render_case_report(CASE,state))
        self.assertIn('Simulated acceptance recorded; no real repair certification',render_case_report(CASE,state))
        self.assertIn('已授权；未扣款',render_case_report(CASE,state,'zh-CN'))
    def test_sensitive_fields_values_and_local_paths_are_omitted(self):
        state=copy.deepcopy(STATE)
        state.update(csrf='CSRF-DO-NOT-PRINT',create_request_id='REQUEST-DO-NOT-PRINT',client_secret='SECRET-DO-NOT-PRINT',private_path=r'C:\Users\Private\vault.txt')
        state['payment']['approval_url']='https://www.sandbox.paypal.com/?token=APPROVAL-DO-NOT-PRINT'
        state['review']['note']='Keep original wording. '+state['client_secret']+'\n'+r'C:\Users\Private\with spaces\file.csv'+'\n/home/private/key.pem\npassword=INLINE-PASSWORD\nBearer INLINE-TOKEN'
        report=render_case_report(CASE,state)
        for private in ('CSRF-DO-NOT-PRINT','REQUEST-DO-NOT-PRINT','SECRET-DO-NOT-PRINT','APPROVAL-DO-NOT-PRINT','Private','/home/private','INLINE-PASSWORD','INLINE-TOKEN'):
            self.assertNotIn(private,report)
        self.assertIn('Keep original wording.',report)
        self.assertIn('[local path omitted]',report)
        self.assertIn('[redacted]',report)
    def test_legacy_state_has_no_fabricated_versions_or_dates(self):
        legacy={'review':{'decision':'observe','note':NOTE},'repair':'unverified','history':[]}
        report=render_case_report(CASE,legacy)
        self.assertIn('no history has been reconstructed',report)
        self.assertIn('No structured evidence versions have been recorded',report)
        self.assertNotRegex(report,r'20\d\d-\d\d-\d\d')
        self.assertIn(NOTE,report)
    def test_structured_versions_include_both_decisions_and_honest_legacy_origin(self):
        state=copy.deepcopy(STATE)
        state['evidence_history_origin']='legacy_unversioned'
        state['evidence_history']=[{'version':1,'recorded_at':'2026-10-11T00:00:00Z','action':'review','before_origin':'legacy_state_observed_at_update','before':{'review':{'decision':'observe','note':'Earlier exact note'},'repair':'unverified'},'after':{'review':{'decision':'replace','note':'Later exact note'},'repair':'unverified'},'case_evidence_sha256':'a'*64,'after_sha256':'b'*64}]
        report=render_case_report(CASE,state)
        for text in ('Before this update','After this update','Earlier exact note','Later exact note','Continue observing','Out-of-warranty replacement / service','Its original event time is unknown.','a'*64,'b'*64):
            self.assertIn(text,report)
    def test_renderer_is_deterministic_and_does_not_mutate_inputs(self):
        case,state=copy.deepcopy(CASE),copy.deepcopy(STATE)
        before=copy.deepcopy((case,state))
        first=render_case_report(case,state,'en')
        self.assertEqual(first,render_case_report(case,state,'unsupported-locale'))
        self.assertEqual((case,state),before)
        self.assertIn('does not grant permission to publish research data',first)
    def test_print_css_matches_exported_csp_without_active_content(self):
        report=render_case_report(CASE,STATE)
        styles=re.findall(r'<style>(.*?)</style>',report,re.S)
        self.assertEqual(styles,[REPORT_CSS])
        digest=base64.b64encode(hashlib.sha256(styles[0].encode()).digest()).decode()
        self.assertEqual(REPORT_STYLE_CSP,"'sha256-"+digest+"'")
        self.assertIn(REPORT_STYLE_CSP,REPORT_CSP)
        self.assertNotIn('unsafe-inline',REPORT_CSP)
        self.assertIn('@media print',report)
        parsed=ParsedHTML();parsed.feed(report)
        self.assertFalse(any(tag in ('script','iframe','form','input','object') for tag,_ in parsed.tags))
        self.assertFalse(any('src' in attrs or 'href' in attrs for _,attrs in parsed.tags))
    def test_warranty_and_legacy_capture_are_not_misrepresented_as_completed_service(self):
        state=copy.deepcopy(STATE)
        state['review']['decision']='warranty'
        state['payment']['intent']='CAPTURE'
        report=render_case_report(CASE,state)
        self.assertIn('Warranty request is a draft',report)
        self.assertIn('Legacy payment record',report)
        self.assertIn('Not accepted / unverified',report)
    def test_sparse_state_renders_without_inventing_success(self):
        report=render_case_report({'id':'OLD'}, {})
        self.assertIn('Not recorded',report)
        self.assertIn('Not accepted / unverified',report)
        self.assertNotIn('Charge recorded',report)
        self.assertNotIn('All case observations and field checks are synthetic',report)

if __name__=='__main__':unittest.main()
