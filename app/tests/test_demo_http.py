"""HTTP rehearsal isolation, report routes and private-resource boundaries."""
from contextlib import ExitStack
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.request
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server


class DemoHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.db = cls.root / "isolated.sqlite"
        with socket.socket() as sock:
            sock.bind(("127.0.0.1",0));cls.port=sock.getsockname()[1]
        cls.base=f"http://127.0.0.1:{cls.port}"
        cls.stack=ExitStack()
        cls.stack.enter_context(patch.object(server,"ROOT",cls.root))
        cls.env=cls.stack.enter_context(patch.object(server,"load_env",side_effect=AssertionError("Offline service must not read credentials")))
        cls.paypal=cls.stack.enter_context(patch.object(server,"PayPal",side_effect=AssertionError("Offline service must not instantiate live adapter")))
        original=server.ThreadingHTTPServer
        ready=threading.Event()
        def create(*args,**kwargs):
            cls.httpd=original(*args,**kwargs);ready.set();return cls.httpd
        cls.stack.enter_context(patch.object(server,"ThreadingHTTPServer",side_effect=create))
        cls.thread=threading.Thread(target=server.serve,args=(cls.port,cls.db,None,True),daemon=True)
        cls.thread.start()
        if not ready.wait(5):raise RuntimeError("Local test service did not start")

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown();cls.thread.join(5);cls.stack.close();cls.temp.cleanup()

    def get(self,path):
        with urllib.request.urlopen(self.base+path,timeout=5) as response:return json.load(response)

    def test_offline_service_and_unconfigured_model_are_truthful(self):
        result=self.get("/api/health?lang=en")
        self.assertFalse(result["sandbox_configured"])
        self.assertEqual(result["session_mode"],"offline_demo")
        self.assertEqual(self.get("/api/research-inference")["status"],"unconfigured")
        self.env.assert_not_called();self.paypal.assert_not_called()

    def test_reports_are_bilingual_read_only_and_only_allow_known_cases(self):
        before=self.get("/api/cases")
        db_before=self.db.read_bytes()
        for language in ("en","zh-CN"):
            with urllib.request.urlopen(self.base+"/api/cases/FF-102/report?lang="+language,timeout=5) as response:
                html=response.read().decode("utf-8")
                self.assertIn("text/html",response.headers["Content-Type"])
                self.assertIn("sha256-",response.headers["Content-Security-Policy"])
                self.assertIn("FF-102",html)
                self.assertIn('lang="'+language+'"',html)
                self.assertNotIn(before["csrf"],html)
        self.assertEqual(self.db.read_bytes(),db_before)
        for path in ("/api/cases/UNKNOWN/report","/runtime/research-inference.audit.json","/.env","/workflow.py"):
            with self.assertRaises(urllib.error.HTTPError) as failure:
                self.get(path)
            self.assertEqual(failure.exception.code,404)


if __name__ == "__main__":unittest.main()
