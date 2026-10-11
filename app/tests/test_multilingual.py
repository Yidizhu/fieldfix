"""Five-language response/report contract with unchanged evidence and money."""
from copy import deepcopy
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import unittest

APP=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(APP))
from analysis_engine import get_cases, analyze
from case_ai import attach_case_ai
from case_report import render_case_report, TEXT
import locale_extra as extra
import localization as loc
from recovery import evaluate_recovery
import test_ai_http as http_helper

LANGUAGES=('en','zh-CN','es','fr','pt')
NOTE='用户原文不可翻译。 Note originale: revisar só depois. <script>keep as text</script>'
ACCEPT='人工验收原文。 Accepted only after reviewing the synthetic evidence.'

class PlainText(HTMLParser):
    def __init__(self):super().__init__();self.parts=[];self.tags=[]
    def handle_data(self,data):self.parts.append(data)
    def handle_starttag(self,tag,attrs):self.tags.append(tag)

def evidence_fields(case):
    result=deepcopy(case)
    for key in ('title','site','device_names','workflow'):result.pop(key,None)
    for device in result.get('series',[]):device.pop('name',None)
    for key in ('summary','method','evidence','next_steps'):result.get('analysis',{}).pop(key,None)
    return result

def raw_workflow(state):
    result=deepcopy(state);result.pop('locale',None)
    for event in result.get('history',[]):event.pop('display_text',None)
    if isinstance(result.get('recovery'),dict):result['recovery'].pop('display_explanation',None)
    return result

class MultilingualTests(unittest.TestCase):
    def test_complete_fixed_catalogues_without_implicit_language_fallback(self):
        catalogues=((loc.SYSTEM_TEXT,loc.SYSTEM_EXTRA),(loc.ERROR_TEXT,extra.ERRORS),
                    (loc.HISTORY_TEXT,extra.HISTORY),(loc.HISTORY_PREFIXES,extra.PREFIXES),(TEXT,extra.REPORT))
        for source,translations in catalogues:
            self.assertFalse(set(source)-set(translations))
            for key in source:
                for language in ('es','fr','pt'):
                    value=translations[key][language]
                    self.assertTrue(value.strip(),(key,language))
                    self.assertFalse(re.search(r'[\u3400-\u9fff]',value),(key,language))
        self.assertEqual(set(extra.PATTERNS),{str(i) for i in range(len(loc.ANALYSIS_PATTERNS))})

    def test_regional_aliases_and_api_report_default_remain_separate(self):
        for language in LANGUAGES:
            self.assertEqual(loc.normalize_locale(language),language)
        for alias,expected in (('ES_mx','es'),('fr-CA','fr'),('pt-BR','pt'),('pt-PT','pt'),('en-NZ','en'),('zh-Hant','zh-CN')):
            self.assertEqual(loc.normalize_locale(alias),expected)
        self.assertEqual(loc.normalize_locale('de'),'zh-CN')
        self.assertIn('lang="en"',render_case_report({}, {}, 'de'))
        self.assertIn('lang="fr"',render_case_report({}, {}, 'fr-CA'))

    def test_real_case_translations_preserve_observations_ai_hashes_and_custom_text(self):
        cases=[attach_case_ai(case) for case in get_cases()];original=deepcopy(cases)
        for case in cases:
            for language in LANGUAGES:
                translated=loc.localize_case(case,language)
                self.assertEqual(evidence_fields(translated),evidence_fields(case))
                self.assertEqual(translated['ai'],case['ai'])
                if language!='zh-CN':
                    generated=[translated['title'],translated['site'],translated['analysis']['summary'],translated['analysis']['method']]+translated['analysis']['evidence']+translated['analysis']['next_steps']
                    self.assertFalse(any(re.search(r'[\u3400-\u9fff]',value) for value in generated),generated)
                if language in ('es','fr','pt'):
                    self.assertNotEqual(translated['title'],loc.localize_case(case,'en')['title'])
        custom=deepcopy(cases[0]);custom['title']=NOTE;custom['site']=NOTE;custom['series'][0]['name']=NOTE
        for language in LANGUAGES:
            translated=loc.localize_case(custom,language)
            self.assertEqual(translated['title'],NOTE);self.assertEqual(translated['site'],NOTE)
            self.assertEqual(translated['series'][0]['name'],NOTE)
        self.assertEqual(cases,original)

    def test_parameterized_evidence_preserves_thresholds_windows_and_counts(self):
        for language in ('es','fr','pt'):
            shifted=loc.localize_case(get_cases()[1],language)['analysis']['evidence'][0]
            for value in ('48','24','±4.0'):self.assertIn(value,shifted)
            shared=loc.localize_case(get_cases()[0],language)['analysis']['evidence']
            self.assertIn('GW-NORTH',shared[0]);self.assertIn('2026-10-03 12:00 UTC',shared[1]);self.assertIn('12, 12, 12',shared[2])
            device=deepcopy(get_cases()[1]['series'][1])
            for point in device['points'][48:54]:point['value']-=9
            output=loc.localize_analysis(analyze([device]),language,{'探头 2':'CUSTOM-NAME'})
            self.assertIn('18',output['evidence'][0]);self.assertIn('CUSTOM-NAME',output['evidence'][0])
            self.assertFalse(re.search(r'[\u3400-\u9fff]',json.dumps(output,ensure_ascii=False)))

    def test_all_system_errors_have_selected_translation_and_unknown_errors_do_not_leak_notes(self):
        for original,english in loc.ERROR_TEXT.items():
            self.assertEqual(loc.localize_error(original,'en'),english)
            self.assertEqual(loc.localize_error(original,'zh-CN'),original)
            for language in ('es','fr','pt'):
                self.assertEqual(loc.localize_error(original,language),extra.ERRORS[original][language])
        for language in ('en','es','fr','pt'):
            self.assertNotIn(NOTE,loc.localize_error(NOTE,language))

    def test_original_notes_history_recovery_values_and_versions_never_change(self):
        for scenario in ('recovered','still_faulty','insufficient'):
            recovery=evaluate_recovery(scenario);recovery['human_review']={'note':NOTE,'at':'2026-10-11T00:00:00Z'}
            state={'review':{'decision':'observe','note':NOTE},'repair':'unverified','recovery':recovery,
                   'payment':{'amount':'25.00','currency':'NZD','order_id':'ORDER-UNCHANGED','status':'authorized'},
                   'evidence_history':[{'before':{'review':{'note':NOTE}},'after':{'recovery':recovery}}],
                   'history':[{'at':'2026-10-11T00:00:00Z','text':prefix+NOTE} for prefix in loc.HISTORY_PREFIXES]+
                             [{'text':text} for text in loc.HISTORY_TEXT]+[{'text':NOTE}]}
            original=deepcopy(state)
            for language in LANGUAGES:
                result=loc.localize_workflow(state,language)
                self.assertEqual(raw_workflow(result),original)
                for event in result['history'][:3]:self.assertTrue(event['display_text'].endswith(NOTE))
                self.assertTrue(result['history'][-1]['display_text'].endswith(NOTE))
                if language in ('es','fr','pt'):
                    self.assertEqual(result['recovery']['display_explanation'],extra.RECOVERY[recovery['status']][language])
            self.assertEqual(state,original)
        unknown={'recovery':{'explanation':NOTE,'status':'pass'},'history':[]}
        for language in LANGUAGES:
            self.assertEqual(loc.localize_workflow(unknown,language)['recovery']['display_explanation'],NOTE)

    def test_unknown_evidence_remains_original_and_report_keeps_html_safe(self):
        source={'category':'normal','summary':NOTE,'method':NOTE,'evidence':[NOTE],'next_steps':[]}
        for language in LANGUAGES:
            translated=loc.localize_analysis(source,language)
            self.assertIn(NOTE,translated['summary']);self.assertIn(NOTE,translated['evidence'][0])
            report=render_case_report({'id':'CUSTOM','title':NOTE,'analysis':source}, {'review':{'note':NOTE}},language)
            parsed=PlainText();parsed.feed(report)
            self.assertNotIn('script',parsed.tags);self.assertIn(NOTE,''.join(parsed.parts))

    def test_five_language_http_flow_and_downloads_preserve_same_bound_evidence(self):
        fixture=http_helper.AIHttpTests()
        for language in LANGUAGES:
            with self.subTest(language=language),fixture.service() as client:
                payload=client.cases(language);case=next(item for item in payload['cases'] if item['id']=='FF-102')
                self.assertEqual(payload['locale'],language);ai=case['ai']
                def post(action,body,status=200):
                    return client.request('/api/cases/FF-102/'+action+'?lang='+language,body,status)[0]
                error=post('capture',{'confirmed':True},409)
                self.assertEqual(error['locale'],language)
                if language!='zh-CN':self.assertFalse(re.search(r'[\u3400-\u9fff]',error['error']))
                reviewed=post('review',{'decision':'replace','note':NOTE,'confirmed':True})
                self.assertEqual(reviewed['review']['note'],NOTE);self.assertEqual(reviewed['ai_review'],ai)
                approved=post('approve',{'confirmed':True});self.assertEqual(approved['quote']['amount'],'25.00')
                post('rehearse',{})
                recovery=post('submit_recovery',{'scenario':'recovered'})
                self.assertEqual(recovery['repair'],'unverified')
                post('verify_repair',{'confirmed':True,'note':ACCEPT})
                paid=post('capture',{'confirmed':True})
                self.assertEqual(paid['payment']['amount'],'25.00');self.assertEqual(paid['payment']['currency'],'NZD')
                self.assertEqual(paid['payment']['mode'],'local_rehearsal');self.assertEqual(paid['ai_review'],ai)
                before=client.db.read_bytes()
                report,headers=client.report(language)
                self.assertIn('lang="'+language+'"',report)
                self.assertIn('sha256-',headers['Content-Security-Policy'])
                for value in (ai['model']['sha256'],ai['inputs_sha256'],ai['evidence_sha256'],'25.00','NZD'):self.assertIn(value,report)
                parsed=PlainText();parsed.feed(report);plain=''.join(parsed.parts)
                self.assertIn(NOTE,plain);self.assertIn(ACCEPT,plain);self.assertNotIn('script',parsed.tags)
                if language!='zh-CN':self.assertFalse(re.search(r'[\u3400-\u9fff]',plain.replace(NOTE,'').replace(ACCEPT,'')))
                if language in ('es','fr','pt'):
                    for key in ('title','ai_details','mean_absolute_error','ai_input_hash','local_rehearsal'):
                        self.assertIn(extra.REPORT[key][language],plain)
                    self.assertNotIn('Model identifiers and original signal sources',plain)
                self.assertEqual(client.db.read_bytes(),before)
                self.assertEqual(client.adapter.calls,[])

if __name__=='__main__':unittest.main()