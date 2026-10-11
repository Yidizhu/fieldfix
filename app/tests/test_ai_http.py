"""Four end-to-end AI/HTTP checks; all provider responses are controlled fakes.

The real frozen classifier and case attachment run in server.serve. Only loopback
HTTP is permitted, credentials are never read, and every database is temporary.
"""
from contextlib import ExitStack, contextmanager
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server
from case_ai import attach_case_ai
from analysis_engine import get_cases

PROJECT = Path(__file__).resolve().parents[2]
NOTE = '人工原话：核对合成观测和现场检查演练，记录人工决定。'
ACCEPT = '人工原话：已独立检查模拟恢复数据，再确认本次演练验收。'


class FakePayPal:
    """Lifecycle contract only: this does not test or contact the PayPal API."""
    def __init__(self, configured):
        self.configured = configured
        self.calls = []
    def record(self, action, *args):
        if not self.configured:
            raise AssertionError('Offline rehearsal must never call a payment adapter')
        self.calls.append((action, *args))
    def create(self, case_id, amount, request_id):
        self.record('create', case_id, amount, request_id)
        return {'status':'awaiting_buyer','order_id':'FAKE-SANDBOX-ORDER'}
    def authorize(self, order_id, case_id, amount, request_id):
        self.record('authorize', order_id, case_id, amount, request_id)
        return {'status':'authorized','authorization_id':'FAKE-SANDBOX-AUTH',
                'authorized_at':datetime.now(timezone.utc).isoformat(),
                'expires_at':(datetime.now(timezone.utc)+timedelta(days=29)).isoformat()}
    def capture_authorization(self, order_id, authorization_id, case_id, amount, request_id, checkpoint=None, capture_id=None):
        self.record('capture', order_id, authorization_id, case_id, amount, request_id)
        if checkpoint:
            checkpoint({'capture_id':'FAKE-SANDBOX-CAPTURE'})
        return {'status':'completed','capture_id':'FAKE-SANDBOX-CAPTURE'}
    def void_authorization(self, *args):
        raise AssertionError('This fixture does not implement provider void')
    def reconcile(self, *args):
        raise AssertionError('This fixture does not implement provider reconcile')


class Client:
    def __init__(self, base, db, adapter):
        self.base, self.db, self.adapter = base, db, adapter
        self.csrf = None
        self.request_count = 0
    def request(self, path, body=None, status=200):
        headers = {}
        data = None
        if body is not None:
            data=json.dumps(body, ensure_ascii=False).encode('utf-8')
            headers={'Content-Type':'application/json','X-FieldFix-Token':self.csrf or '', 'Origin':self.base}
        request=urllib.request.Request(self.base+path, data=data, headers=headers)
        self.request_count += 1
        try:
            response=urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as error:
            response=error
        with response:
            code=response.code; raw=response.read().decode('utf-8'); content_type=response.headers.get('Content-Type','')
            result=json.loads(raw) if 'application/json' in content_type else raw
            if code != status:
                raise AssertionError(f'{path}: expected HTTP {status}, received {code}: {result}')
            if isinstance(result,dict) and result.get('csrf'):
                self.csrf=result['csrf']
            return result,dict(response.headers)
    def cases(self, language='en'):
        return self.request('/api/cases?lang='+language)[0]
    def act(self, action, body=None, status=200, case_id='FF-102'):
        return self.request('/api/cases/'+case_id+'/'+action+'?lang=en',{} if body is None else body,status)[0]
    def report(self, language='en'):
        return self.request('/api/cases/FF-102/report?lang='+language)


class AIHttpTests(unittest.TestCase):
    @contextmanager
    def service(self, *, missing_model=False, fake_sandbox=False):
        temp_root=PROJECT/'work'/'test-temp'
        temp_root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='fieldfix-ai-http-',dir=temp_root) as temporary, ExitStack() as stack:
            root=Path(temporary);db=root/'isolated.sqlite'
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            base=f'http://127.0.0.1:{port}'
            fake=FakePayPal(fake_sandbox)
            stack.enter_context(patch.object(server,'ROOT',root))
            credentials=stack.enter_context(patch.object(server,'load_env',side_effect=(None if fake_sandbox else AssertionError('Credentials must not be read'))))
            real_adapter=stack.enter_context(patch.object(server,'PayPal',return_value=fake))
            offline_adapter=stack.enter_context(patch.object(server,'OfflinePayPal',return_value=fake))
            attached=stack.enter_context(patch.object(server,'attach_case_ai',wraps=attach_case_ai))
            real_urlopen=urllib.request.urlopen
            def local_only(request,*args,**kwargs):
                target=urlsplit(request.full_url if isinstance(request,urllib.request.Request) else str(request))
                if target.scheme != 'http' or target.hostname != '127.0.0.1' or target.port != port:
                    raise AssertionError('External network access is forbidden by this test')
                return real_urlopen(request,*args,**kwargs)
            stack.enter_context(patch.object(urllib.request,'urlopen',side_effect=local_only))
            original=server.ThreadingHTTPServer;ready=threading.Event();holder={};failures=[]
            def create(*args,**kwargs):
                holder['httpd']=original(*args,**kwargs);ready.set();return holder['httpd']
            stack.enter_context(patch.object(server,'ThreadingHTTPServer',side_effect=create))
            def start():
                try:
                    server.serve(port,db,None,not fake_sandbox,None,root/'missing-model.json' if missing_model else None)
                except BaseException as error:
                    failures.append(error);ready.set()
            thread=threading.Thread(target=start,daemon=True)
            thread.start()
            try:
                if not ready.wait(10):raise AssertionError('Local test service did not start')
                if failures:raise AssertionError(f'Local test service failed: {failures[0]}')
                yield Client(base,db,fake)
                self.assertEqual(attached.call_count,3)
                self.assertEqual(real_adapter.call_count,1 if fake_sandbox else 0)
                self.assertEqual(offline_adapter.call_count,0 if fake_sandbox else 1)
                self.assertEqual(credentials.call_count,1 if fake_sandbox else 0)
            finally:
                if 'httpd' in holder:holder['httpd'].shutdown()
                thread.join(5)
                self.assertFalse(thread.is_alive(),'Local test service did not shut down')

    def ready_case(self, client):
        response=client.cases()
        case=next(case for case in response['cases'] if case['id']=='FF-102')
        self.assertEqual(case['ai']['status'],'ready')
        self.assertTrue(case['ai']['model_executed'])
        self.assertEqual(case['ai']['model']['training_data'],'synthetic')
        self.assertEqual(case['analysis']['category'],'reading_anomaly')
        self.assertIsNone(case['workflow']['review']);self.assertIsNone(case['workflow']['payment'])
        return case
    def review_and_approve(self, client):
        review=client.act('review',{'decision':'replace','note':NOTE,'confirmed':True})
        self.assertIsNone(review['payment']);self.assertFalse(review['approved'])
        approved=client.act('approve',{'confirmed':True})
        self.assertEqual(approved['quote']['amount'],'25.00');self.assertEqual(approved['quote']['currency'],'NZD')
        self.assertEqual(client.act('approve',{'confirmed':True}),approved)
        return approved
    def assert_reports(self, client, state, evidence):
        before=client.db.read_bytes()
        for language in ('en','zh-CN'):
            html,headers=client.report(language)
            self.assertIn('text/html',headers['Content-Type'])
            self.assertIn('sha256-',headers['Content-Security-Policy'])
            self.assertIn('lang="'+language+'"',html)
            self.assertIn(NOTE,html);self.assertIn(ACCEPT,html)
            self.assertNotIn(client.csrf,html)
            for digest in (evidence['model']['sha256'],evidence['inputs_sha256'],evidence['evidence_sha256']):
                self.assertIn(digest,html)
            self.assertNotIn(str(client.db),html)
        self.assertEqual(client.db.read_bytes(),before,'Report GET must be read-only')
        for language in ('en','zh-CN'):
            case=next(case for case in client.cases(language)['cases'] if case['id']=='FF-102')
            self.assertEqual(case['workflow']['ai_review'],evidence)
            self.assertEqual(case['workflow']['payment'],state['payment'])
            self.assertEqual(case['ai']['evidence_sha256'],evidence['evidence_sha256'])

    def test_real_ai_to_local_settlement_gates_idempotency_and_bilingual_report(self):
        with self.service() as client:
            case=self.ready_case(client);evidence=case['ai']
            client.act('capture',{'confirmed':True},409)
            client.act('review',{'decision':'replace','note':NOTE,'confirmed':False},409)
            approved=self.review_and_approve(client)
            self.assertEqual(approved['ai_review'],evidence)
            authorized=client.act('rehearse')
            self.assertEqual(authorized['payment']['status'],'authorized')
            self.assertEqual(authorized['payment']['mode'],'local_rehearsal')
            self.assertEqual(client.act('rehearse'),authorized)
            for scenario,expected in (('still_faulty','fail'),('insufficient','insufficient')):
                result=client.act('submit_recovery',{'scenario':scenario})
                self.assertEqual(result['recovery']['status'],expected)
                self.assertEqual(result['repair'],'unverified')
                client.act('verify_repair',{'note':ACCEPT,'confirmed':True},409)
                client.act('capture',{'confirmed':True},409)
            passed=client.act('submit_recovery',{'scenario':'recovered'})
            self.assertEqual(passed['recovery']['status'],'pass');self.assertEqual(passed['repair'],'unverified')
            self.assertEqual(passed['payment']['status'],'authorized')
            client.act('capture',{'confirmed':True},409)
            client.act('verify_repair',{'note':ACCEPT,'confirmed':False},409)
            accepted=client.act('verify_repair',{'note':ACCEPT,'confirmed':True})
            self.assertEqual(accepted['repair'],'verified_demo')
            self.assertEqual(client.act('verify_repair',{'note':ACCEPT,'confirmed':True}),accepted)
            client.act('capture',{'confirmed':False},409)
            paid=client.act('capture',{'confirmed':True})
            self.assertEqual(paid['payment']['status'],'completed')
            self.assertEqual(paid['payment']['mode'],'local_rehearsal')
            self.assertEqual(client.act('capture',{'confirmed':True}),paid)
            self.assertEqual(len(paid['evidence_history']),5)
            self.assertEqual(paid['evidence_history'][0]['after']['ai_review'],evidence)
            self.assert_reports(client,paid,evidence)
            self.assertEqual(client.adapter.calls,[])

    def test_missing_model_and_forged_request_cannot_buy_but_observation_is_allowed(self):
        forged=attach_case_ai(get_cases()[1])['ai']
        self.assertEqual(forged['status'],'ready')
        with self.service(missing_model=True) as client:
            case=next(case for case in client.cases()['cases'] if case['id']=='FF-102')
            self.assertEqual(case['ai']['status'],'unavailable')
            self.assertEqual(case['analysis']['category'],'insufficient_data')
            for decision in ('replace','warranty'):
                client.act('review',{'decision':decision,'note':NOTE,'confirmed':True,'ai':forged,
                    'ai_review':forged,'analysis':{'category':'reading_anomaly'}},409)
            for action in ('approve','rehearse','create_order'):
                client.act(action,{'confirmed':True,'ai':forged,'ai_review':forged,'approved':True},409)
            observed=client.act('review',{'decision':'observe','note':NOTE,'confirmed':True,'ai':forged})
            self.assertEqual(observed['ai_review']['status'],'unavailable')
            self.assertFalse(observed['approved']);self.assertIsNone(observed['payment'])
            client.act('approve',{'confirmed':True,'ai':forged},409)
            for language in ('en','zh-CN'):
                report,_=client.report(language)
                self.assertNotIn('recorded local model inference completed',report)
                self.assertNotIn('已记录本地模型实际推断结果',report)
            self.assertEqual(client.adapter.calls,[])

    def test_fake_sandbox_lifecycle_uses_same_bound_ai_without_real_paypal(self):
        with self.service(fake_sandbox=True) as client:
            case=self.ready_case(client);evidence=case['ai']
            self.review_and_approve(client)
            created=client.act('create_order')
            self.assertEqual(created['payment']['status'],'awaiting_buyer')
            self.assertEqual(client.act('create_order'),created)
            authorized=client.act('authorize')
            self.assertEqual(authorized['payment']['status'],'authorized')
            self.assertEqual(client.act('authorize'),authorized)
            self.assertEqual(authorized['repair'],'unverified')
            client.act('capture',{'confirmed':True},409)
            client.act('submit_recovery',{'scenario':'recovered'})
            client.act('verify_repair',{'note':ACCEPT,'confirmed':True})
            paid=client.act('capture',{'confirmed':True})
            self.assertEqual(paid['payment']['status'],'completed')
            self.assertEqual(paid['payment']['capture_id'],'FAKE-SANDBOX-CAPTURE')
            self.assertEqual(client.act('capture',{'confirmed':True}),paid)
            self.assertEqual([call[0] for call in client.adapter.calls],['create','authorize','capture'])
            self.assert_reports(client,paid,evidence)

    def test_shared_dropout_and_normal_ai_cannot_be_recast_as_paid_replacement(self):
        with self.service() as client:
            cases={case['id']:case for case in client.cases()['cases']}
            self.assertEqual(cases['FF-101']['ai']['summary_code'],'shared_dropout')
            self.assertEqual(cases['FF-103']['ai']['summary_code'],'normal')
            for case_id,decision in (('FF-101','inspect_connection'),('FF-103','observe')):
                self.assertEqual(cases[case_id]['ai']['status'],'ready')
                for invalid in ('replace','warranty'):
                    client.act('review',{'decision':invalid,'note':NOTE,'confirmed':True,
                        'analysis':{'category':'reading_anomaly'},'ai':cases['FF-102']['ai']},409,case_id)
                reviewed=client.act('review',{'decision':decision,'note':NOTE,'confirmed':True},case_id=case_id)
                self.assertEqual(reviewed['ai_review'],cases[case_id]['ai'])
                client.act('approve',{'confirmed':True},409,case_id)
                self.assertIsNone(reviewed['payment']);self.assertEqual(reviewed['repair'],'unverified')
            self.assertEqual(client.adapter.calls,[])


if __name__=='__main__':unittest.main()