"""Language tests cover decision invariants, actual API routing and note integrity."""
import ast
from contextlib import ExitStack
import copy
import json
from pathlib import Path
import re
import socket
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

APP = Path(__file__).resolve().parents[1]
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from analysis_engine import analyze, get_cases
from localization import (ERROR_TEXT, localize_analysis, localize_case,
                          localize_error, localize_response, localize_workflow,
                          normalize_locale)
import server


def immutable_case_fields(case):
    return {
        'id': case['id'], 'gateway_id': case['gateway_id'],
        'provenance': case['provenance'],
        'series': [{key: value for key, value in device.items() if key != 'name'}
                   for device in case['series']],
        'analysis': {key: value for key, value in case['analysis'].items()
                     if key not in ('summary', 'method', 'evidence', 'next_steps')},
    }


def original_workflow_fields(state):
    result = copy.deepcopy(state)
    result.pop('locale', None)
    for event in result.get('history', []):
        event.pop('display_text', None)
    return result


class LocalizationTests(unittest.TestCase):
    def test_language_changes_no_measurements_decisions_ids_or_times(self):
        cases = get_cases()
        before = copy.deepcopy(cases)
        for case in cases:
            chinese = localize_case(case, 'zh-CN')
            english = localize_case(case, 'en')
            self.assertEqual(immutable_case_fields(chinese), immutable_case_fields(english))
            self.assertEqual(immutable_case_fields(case), immutable_case_fields(english))
            self.assertNotEqual(chinese['title'], english['title'])
            self.assertNotEqual(chinese['site'], english['site'])
            self.assertEqual(english['series'][0]['name'], 'Probe 1')
            self.assertEqual(english['device_names'][0], 'Probe 1')
        self.assertEqual(cases, before)

    def test_all_demo_analysis_text_is_english_and_detailed(self):
        for case in get_cases():
            translated = localize_case(case, 'en')['analysis']
            lines = [translated['summary'], translated['method']] + translated['evidence'] + translated['next_steps']
            self.assertFalse(any(re.search(r'[\u3400-\u9fff]', text) for text in lines), lines)
            self.assertFalse(any('translation unavailable' in text for text in lines))
        shifted = localize_case(get_cases()[1], 'en')['analysis']['evidence'][0]
        self.assertIn('Probe 2', shifted)
        self.assertIn('48 valid historical points', shifted)
        self.assertIn('24 subsequent valid points', shifted)
        self.assertIn('24 consecutive hours', shifted)
        self.assertIn('±4.0', shifted)
        shared = localize_case(get_cases()[0], 'en')['analysis']['evidence']
        self.assertIn('GW-NORTH', shared[0])
        self.assertIn('2026-10-03 12:00 UTC', shared[1])
        self.assertIn('12, 12, 12', shared[2])

    def test_dynamic_parameters_are_not_replaced_by_category_summary(self):
        device = copy.deepcopy(get_cases()[1]['series'][1])
        for point in device['points'][48:54]:
            point['value'] -= 9
        result = analyze([device])
        english = localize_analysis(result, 'en', {'探头 2': 'Probe 2'})
        self.assertIn('连续18小时', result['evidence'][0])
        self.assertIn('18 consecutive hours', english['evidence'][0])
        self.assertNotIn('24 consecutive hours', english['evidence'][0])

    def test_insufficient_and_timing_evidence_remain_specific(self):
        for kind in ('empty', 'unknown_gateway', 'short', 'irregular'):
            if kind == 'empty':
                devices = []
            elif kind == 'unknown_gateway':
                devices = get_cases()[0]['series']
                for device in devices:
                    device['gateway_id'] = None
            else:
                devices = get_cases()[2]['series'][:1]
                if kind == 'short':
                    devices[0]['points'] = devices[0]['points'][:20]
                else:
                    del devices[0]['points'][52]
            result = localize_analysis(analyze(devices), 'en',
                                       {f'探头 {i}': f'Probe {i}' for i in range(1, 4)})
            self.assertEqual(result['category'], 'insufficient_data')
            text = json.dumps(result, ensure_ascii=False)
            self.assertNotIn('translation unavailable', text)
            self.assertFalse(re.search(r'[\u3400-\u9fff]', text), text)

    def test_original_human_notes_and_old_history_are_preserved(self):
        note = '探头仍需复查；already approved? 不要购买。 <script>sample</script>'
        state = {'review': {'decision': 'observe', 'note': note, 'simulated': True},
                 'approved': False, 'payment': {'amount': '25.00', 'currency': 'NZD',
                    'order_id': 'ORDER123', 'status': 'awaiting_buyer'},
                 'repair': 'unverified', 'history': [
                     {'at': '2026-10-08T01:02:03Z', 'text': '人工复核已记录（模拟现场检查）：' + note},
                     {'at': '2026-10-08T02:02:03Z', 'text': '模拟复查已记录，非真实维修：' + note},
                     {'at': '2026-10-08T03:02:03Z', 'text': '用户自己写的旧记录：' + note},
                 ]}
        original = copy.deepcopy(state)
        translated = localize_workflow(state, 'en')
        self.assertEqual(translated['review']['note'], note)
        self.assertEqual(original_workflow_fields(translated), original)
        self.assertTrue(all(event['display_text'].endswith(note) for event in translated['history']))
        self.assertIn('Human review recorded', translated['history'][0]['display_text'])
        self.assertIn('original text', translated['history'][2]['display_text'])
        self.assertEqual(state, original)
        self.assertEqual(localize_workflow(state, 'zh-CN')['history'][0]['display_text'], state['history'][0]['text'])

    def test_unknown_language_falls_back_to_original_chinese(self):
        case = get_cases()[0]
        for value in (None, '', 'de', 'zh-Hant', 'unknown', 'enough'):
            self.assertEqual(normalize_locale(value), 'zh-CN')
            self.assertEqual(localize_case(case, value), case)
        for value in ('en', 'en-NZ', 'EN_us'):
            self.assertEqual(normalize_locale(value), 'en')

    def test_unknown_errors_are_safe_english_not_guessed_user_translation(self):
        source = '客户张三说已经买了，但是不清楚结果。'
        translated = localize_error(source, 'en')
        self.assertIn('could not be completed', translated)
        self.assertNotIn(source, translated)
        self.assertEqual(localize_error(source, 'zh-CN'), source)

    def test_every_current_system_exception_has_an_explicit_translation(self):
        for filename in ('workflow.py', 'paypal.py'):
            tree = ast.parse((APP / filename).read_text(encoding='utf-8-sig'))
            for node in ast.walk(tree):
                if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
                    if node.exc.args and isinstance(node.exc.args[0], ast.Constant):
                        message = node.exc.args[0].value
                        if isinstance(message, str):
                            self.assertIn(message, ERROR_TEXT, (filename, message))
        for original, translated in ERROR_TEXT.items():
            self.assertEqual(localize_error(original, 'en'), translated)
            self.assertFalse(re.search(r'[\u3400-\u9fff]', translated), translated)

    def test_unknown_evidence_is_preserved_not_guessed(self):
        result = {'category': 'normal', 'summary': '未来新增的证据说明',
                  'evidence': ['读数53.7，来源尚待验证'], 'next_steps': [], 'method': '新方法'}
        translated = localize_analysis(result, 'en')
        self.assertIn(result['summary'], translated['summary'])
        self.assertIn(result['evidence'][0], translated['evidence'][0])
        self.assertEqual(translated['category'], result['category'])


class UnconfiguredPayPal:
    configured = False
    def __init__(self, origin):
        self.origin = origin
    def create(self, *args, **kwargs):
        raise AssertionError('Localization tests must not call PayPal')
    def capture(self, *args, **kwargs):
        raise AssertionError('Localization tests must not call PayPal')


class LocalizationHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='fieldfix-locale-test-')
        cls.root = Path(cls.temp.name)
        (cls.root / 'static').mkdir()
        (cls.root / 'static' / 'i18n.js').write_text('// locale test asset', encoding='utf-8')
        cls.db = cls.root / 'test.sqlite'
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            cls.port = probe.getsockname()[1]
        cls.base = f'http://127.0.0.1:{cls.port}'
        cls.ready = threading.Event()
        real_server = server.ThreadingHTTPServer
        def build_server(*args, **kwargs):
            cls.httpd = real_server(*args, **kwargs)
            cls.ready.set()
            return cls.httpd
        cls.stack = ExitStack()
        cls.stack.enter_context(patch.object(server, 'ROOT', cls.root))
        cls.stack.enter_context(patch.object(server, 'load_env'))
        cls.stack.enter_context(patch.object(server, 'PayPal', UnconfiguredPayPal))
        cls.stack.enter_context(patch.object(server, 'ThreadingHTTPServer', side_effect=build_server))
        cls.thread = threading.Thread(target=server.serve, args=(cls.port, cls.db), daemon=True)
        cls.thread.start()
        if not cls.ready.wait(5):
            raise RuntimeError('Test HTTP server did not start')
        with urllib.request.urlopen(cls.base + '/api/cases') as response:
            cls.token = json.load(response)['csrf']

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.thread.join(timeout=5)
        cls.stack.close()
        cls.temp.cleanup()

    def request(self, path, body=None):
        headers = {}
        if body is not None:
            headers = {'Content-Type': 'application/json', 'X-FieldFix-Token': self.token}
        request = urllib.request.Request(self.base + path,
                    data=None if body is None else json.dumps(body).encode(), headers=headers)
        try:
            response = urllib.request.urlopen(request)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def test_get_languages_share_business_values_and_do_not_write_database(self):
        before = self.db.read_bytes()
        _, english = self.request('/api/cases?lang=en')
        _, chinese = self.request('/api/cases?lang=zh-CN')
        _, fallback = self.request('/api/cases?lang=de')
        self.assertEqual(english['locale'], 'en')
        self.assertEqual(chinese['locale'], 'zh-CN')
        self.assertEqual(fallback['locale'], 'zh-CN')
        self.assertEqual(chinese, fallback)
        for zh, en in zip(chinese['cases'], english['cases']):
            self.assertEqual(immutable_case_fields(zh), immutable_case_fields(en))
            self.assertEqual(original_workflow_fields(zh['workflow']), original_workflow_fields(en['workflow']))
        self.assertEqual(self.db.read_bytes(), before)

    def test_post_returns_localized_history_and_keeps_original_note(self):
        note = '模拟现场复查：保持用户原话。 Leave my wording unchanged.'
        status, state = self.request('/api/cases/FF-102/review?lang=en',
                          {'decision': 'replace', 'confirmed': True, 'note': note})
        self.assertEqual(status, 200)
        self.assertEqual(state['locale'], 'en')
        self.assertEqual(state['review']['note'], note)
        self.assertEqual(state['history'][-1]['text'], '人工复核已记录（模拟现场检查）：' + note)
        self.assertTrue(state['history'][-1]['display_text'].endswith(note))
        self.assertTrue(state['history'][-1]['display_text'].startswith('Human review'))
        self.request('/api/cases/FF-102/approve?lang=en', {'confirmed': True})
        status, paid = self.request('/api/cases/FF-102/rehearse?lang=en', {})
        self.assertEqual(status, 200)
        self.assertEqual(paid['payment']['amount'], '25.00')
        self.assertEqual(paid['payment']['currency'], 'NZD')
        self.assertEqual(paid['payment']['mode'], 'local_rehearsal')
        self.assertEqual(paid['repair'], 'unverified')
        self.assertEqual(paid['payment']['status'], 'authorized')
        self.assertIn('no funds were held or charged', paid['history'][-1]['display_text'])

    def test_errors_follow_requested_locale(self):
        code, result = self.request('/api/cases/FF-101/approve?lang=en', {'confirmed': True})
        self.assertEqual(code, 409)
        self.assertEqual(result['locale'], 'en')
        self.assertIn('human inspection', result['error'])
        code, result = self.request('/no-such-page?lang=en')
        self.assertEqual(code, 404)
        self.assertEqual(result['error'], 'Page not found.')

    def test_i18n_script_is_explicitly_served(self):
        with urllib.request.urlopen(self.base + '/i18n.js') as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read(), b'// locale test asset')


if __name__ == '__main__':
    unittest.main()
