import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import Handler

class HttpIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.port=cls.httpd.server_port
        cls.thread=threading.Thread(target=cls.httpd.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def get(self,path):
        with urllib.request.urlopen(f'http://127.0.0.1:{self.port}{path}',timeout=2) as r:
            return r.status,r.read(),r.headers

    def post(self,path,obj):
        req=urllib.request.Request(f'http://127.0.0.1:{self.port}{path}',
           data=json.dumps(obj).encode(),headers={'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(req,timeout=2) as r:return r.status,json.loads(r.read())

    def test_home_page_servable(self):
        status,body,headers=self.get('/')
        self.assertEqual(status,200)
        self.assertIn('STOCKLENS',body.decode())
        self.assertIn('no-referrer',headers['Referrer-Policy'])

    def test_api_health(self):
        status,body,_=self.get('/api/health')
        self.assertEqual(status,200)
        self.assertTrue(json.loads(body)['ok'])

    def test_api_diagnosis(self):
        status,body,_=self.get('/api/diagnosis')
        self.assertEqual(status,200)
        payload=json.loads(body)
        self.assertTrue(payload['metrics']['revenue']['available'])

    def test_api_ask(self):
        status,d=self.post('/api/ask',{'question':'利润为什么下降？'})
        self.assertEqual(status,200)
        self.assertIn('E02',d['evidence_ids'])

    def test_api_pe(self):
        status,d=self.post('/api/pe',{'price':'1313.2'})
        self.assertEqual(status,200)
        self.assertEqual(d['value'],'20.00')

    def test_source_failure_simulation(self):
        status,body,_=self.get('/api/diagnosis?mode=offline')
        self.assertEqual(status,200)
        self.assertFalse(json.loads(body)['metrics']['revenue']['available'])

    def test_invalid_scenario_http_400(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.get('/api/diagnosis?mode=oops')
        self.assertEqual(cm.exception.code,400)

    def test_oversized_request_413(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.post('/api/ask',{'question':'a'*17000})
        self.assertEqual(cm.exception.code,413)

if __name__=='__main__':unittest.main()

class RoutingLLMTests(unittest.TestCase):
    def test_router_without_key_does_not_network(self):
        from unittest.mock import patch
        from server import llm_route
        with patch.dict('os.environ',{'OPENAI_API_KEY':''}), patch('server.urllib.request.urlopen') as mock:
            self.assertIsNone(llm_route('收入'))
            mock.assert_not_called()

    def test_router_with_mocked_valid_llm_response(self):
        from unittest.mock import patch
        from server import llm_route
        from io import BytesIO
        payload={'choices':[{'message':{'content':'{"evidence_ids":["E01","E02"]}'}}]}
        class FakeResponse:
            def __enter__(self):return BytesIO(json.dumps(payload).encode())
            def __exit__(self,*args):return False
        with patch.dict('os.environ',{'OPENAI_API_KEY':'test-key'}), patch('server.urllib.request.urlopen',return_value=FakeResponse()):
            self.assertEqual(llm_route('收入利润'),['E01','E02'])

    def test_router_rejects_hallucinated_id(self):
        from unittest.mock import patch
        from server import llm_route
        from io import BytesIO
        payload={'choices':[{'message':{'content':'{"evidence_ids":["E99"]}'}}]}
        class FakeResponse:
            def __enter__(self):return BytesIO(json.dumps(payload).encode())
            def __exit__(self,*args):return False
        with patch.dict('os.environ',{'OPENAI_API_KEY':'test-key'}),patch('server.urllib.request.urlopen',return_value=FakeResponse()):
            self.assertIsNone(llm_route('ignored'))

    def test_http_ask_structure_has_traced_clauses(self):
        cls=HttpIntegrationTests
        cls.setUpClass()
        try:
            status,resp=cls.post(cls,'/api/ask',{'question':'收入增长为什么利润下降？'})
            self.assertEqual(status,200)
            self.assertTrue(resp['analysis']['facts'])
            self.assertIn('E01',resp['evidence_ids'])
            self.assertIn('E02',resp['evidence_ids'])
        finally:
            cls.tearDownClass()
