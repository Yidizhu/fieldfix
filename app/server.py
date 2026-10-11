"""FieldFix local review prototype. Python 3.10+, no third-party runtime packages."""
import argparse
import json
import mimetypes
import os
from pathlib import Path
import secrets
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlsplit, parse_qs
from analysis_engine import get_cases
from localization import localize_response
from paypal import PayPal, PaymentError
from workflow import Workflow, WorkflowError
from research_replay import read_research
from demo_session import OfflinePayPal, new_demo_database
from case_ai import attach_case_ai

ROOT = Path(__file__).resolve().parent

def load_env():
    path = ROOT.parent / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() in ("PAYPAL_SANDBOX_CLIENT_ID", "PAYPAL_SANDBOX_CLIENT_SECRET"):
                os.environ.setdefault(key.strip(), value.strip().strip(chr(34)).strip(chr(39)))

def serve(port=8765, db_path=None, research_path=None, offline_demo=False, inference_path=None, ai_model_path=None):
    if not offline_demo:
        load_env()
    origin = f"http://127.0.0.1:{port}"
    token = secrets.token_urlsafe(32)
    cases = [attach_case_ai(c, ai_model_path) for c in get_cases()]
    paypal = OfflinePayPal(origin) if offline_demo else PayPal(origin)
    (ROOT / "runtime").mkdir(exist_ok=True)
    if offline_demo and db_path is None:
        db_path = new_demo_database(ROOT / "runtime")
    workflow = Workflow(db_path or ROOT / "runtime" / "fieldfix.sqlite", cases, paypal)
    if offline_demo and any((workflow.snapshot(c["id"]).get("payment") or {}).get("mode") == "paypal_sandbox" for c in cases):
        raise ValueError("A sandbox transaction database cannot be used for offline rehearsal.")
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def reply(self, status, data, content_type="application/json; charset=utf-8", style_source=""):
            if not isinstance(data, bytes):
                language = parse_qs(urlsplit(self.path).query).get("lang", ["zh-CN"])[0]
                data = localize_response(data, language)
            raw = json.dumps(data, ensure_ascii=False).encode() if not isinstance(data, bytes) else data
            self.send_response(status)
            for k,v in {"Content-Type":content_type,"Content-Length":str(len(raw)),"Cache-Control":"no-store",
                "X-Content-Type-Options":"nosniff","Referrer-Policy":"no-referrer",
                "Content-Security-Policy":f"default-src 'self'; script-src 'self'; style-src 'self' {style_source}; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"}.items():self.send_header(k,v)
            self.end_headers()
            self.wfile.write(raw)
        def allowed_host(self):
            return self.headers.get("Host") in (f"127.0.0.1:{port}",f"localhost:{port}")
        def do_GET(self):
            if not self.allowed_host():return self.reply(403,{"error":"仅允许本地访问。"})
            path = urlsplit(self.path).path
            if path == "/api/cases":
                return self.reply(200,{"cases":[dict(c,workflow=workflow.snapshot(c["id"])) for c in cases],
                  "csrf":token,"sandbox_configured":paypal.configured,"data_mode":"synthetic","model_mode":"trained_synthetic_triage","session_mode":"offline_demo" if offline_demo else "sandbox"})
            if path == "/api/health":return self.reply(200,{"status":"ok","sandbox_configured":paypal.configured,"session_mode":"offline_demo" if offline_demo else "sandbox"})
            if path == "/api/research":return self.reply(200,read_research(Path(research_path) if research_path else None))
            if path == "/api/research-inference":
                if not inference_path or not (ROOT / "local_inference.py").is_file():
                    return self.reply(200,{"schema_version":"1.0","mode":"local_frozen_model_inference","status":"unconfigured"})
                from local_inference import read_public_result
                return self.reply(200,read_public_result(Path(inference_path) if inference_path else None))
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[:2] == ["api", "cases"] and parts[3] == "report":
                case = next((c for c in cases if c["id"] == parts[2]), None)
                if case is None:return self.reply(404,{"error":"未找到页面。"})
                from case_report import render_case_report, REPORT_STYLE_CSP
                language = parse_qs(urlsplit(self.path).query).get("lang", ["en"])[0]
                report = render_case_report(case,workflow.snapshot(case["id"]),language)
                return self.reply(200,report.encode("utf-8"),"text/html; charset=utf-8",REPORT_STYLE_CSP)
            files={"/":"index.html","/index.html":"index.html","/app.js":"app.js","/styles.css":"styles.css","/i18n.js":"i18n.js","/research.js":"research.js","/research.css":"research.css","/flow-view.js":"flow-view.js"}
            if path in files:
                f=ROOT/"static"/files[path]
                return self.reply(200,f.read_bytes(), (mimetypes.guess_type(str(f))[0] or "text/plain")+"; charset=utf-8")
            return self.reply(404,{"error":"未找到页面。"})
        def do_POST(self):
            if not self.allowed_host() or self.headers.get("X-FieldFix-Token") != token:
                return self.reply(403,{"error":"请刷新本地页面后再操作。"})
            request_origin=self.headers.get("Origin")
            if request_origin and request_origin not in (origin,f"http://localhost:{port}"):
                return self.reply(403,{"error":"不允许跨站操作。"})
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return self.reply(415,{"error":"请求格式必须为 JSON。"})
            parts=urlsplit(self.path).path.strip("/").split("/")
            if len(parts)!=4 or parts[:2]!=["api","cases"]:return self.reply(404,{"error":"操作不存在。"})
            try:
                length=int(self.headers.get("Content-Length","0"))
                if not 0 < length <= 12000:return self.reply(413,{"error":"请求长度无效。"})
                body=json.loads(self.rfile.read(length))
                if not isinstance(body,dict):raise ValueError()
                result=workflow.act(parts[2],parts[3],body)
                return self.reply(200,result)
            except (WorkflowError, PaymentError) as exc:return self.reply(409,{"error":str(exc)})
            except (ValueError,TypeError):return self.reply(400,{"error":"请求内容无效。"})
            except Exception:return self.reply(500,{"error":"处理未完成。请检查服务日志或稍后重试。"})
    server=ThreadingHTTPServer(("127.0.0.1",port),Handler)
    print(f"FieldFix local preview: {origin}",flush=True)
    print("Data: synthetic | analysis: trained local pattern classifier + independent checks | PayPal: " + ("sandbox configured, unverified" if paypal.configured else "not configured"),flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--port",type=int,default=8765)
    parser.add_argument("--db",help="Optional isolated local test database")
    parser.add_argument("--research",help="Optional private research projection for read-only replay")
    parser.add_argument("--offline-demo",action="store_true",help="Start an isolated local rehearsal without loading or using PayPal credentials")
    parser.add_argument("--inference",help="Optional private results from a verified local frozen-model inference run")
    parser.add_argument("--ai-model",help="Optional local triage model file; unavailable or invalid models block new paid decisions")
    args=parser.parse_args()
    serve(args.port,args.db,args.research,args.offline_demo,args.inference,args.ai_model)

