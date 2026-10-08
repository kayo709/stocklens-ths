"""Run: python server.py  (standard library only, Python 3.10+)."""
from __future__ import annotations
import json
import os
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from diagnostic import build_diagnosis, route_query, scenario_pe, BASE

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / 'static'
ALLOWED = {'normal','missing','conflict','stale','offline'}


def mode_from(query):
    mode = query.get('mode',['normal'])[0]
    if mode not in ALLOWED:
        raise ValueError('未知模拟模式')
    return mode


def llm_route(question: str):
    """Optional OpenAI-compatible intent router: NEVER asks model to compute or write finance claims.

    If unavailable or any invalid output, fail closed to local deterministic router.
    """
    key=os.getenv('OPENAI_API_KEY','').strip()
    if not key:
        return None
    valid=[x['id'] for x in build_diagnosis()['evidence']]
    compact=[{'id':x['id'], 'category':x['category'], 'title':x['title']} for x in build_diagnosis()['evidence']]
    prompt=('仅充当问题到证据ID的路由器。不要计算数字、不要撰写结论、不要输出买卖建议。'
            '仅返回 JSON 对象 {"evidence_ids": ["E01",...]}，最多五个证据ID，'
            '只能选择如下项目：'+json.dumps(compact,ensure_ascii=False))
    payload={'model':os.getenv('OPENAI_MODEL','gpt-4o-mini'), 'temperature':0,
             'response_format':{'type':'json_object'}, 'messages':[{'role':'system','content':prompt},
                            {'role':'user','content':question}], 'max_tokens':160}
    req=urllib.request.Request('https://api.openai.com/v1/chat/completions',
        data=json.dumps(payload,ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type':'application/json','Authorization':'Bearer '+key},method='POST')
    try:
        with urllib.request.urlopen(req,timeout=12) as resp:
            parsed=json.loads(resp.read(65536))
        model_out=json.loads(parsed['choices'][0]['message']['content'])
        ids=model_out.get('evidence_ids')
        if not isinstance(ids,list) or not ids or len(ids)>5 or any(not isinstance(i,str) or i not in valid for i in ids):
            return None
        return list(dict.fromkeys(ids))
    except (ValueError,TypeError,KeyError,IndexError,TimeoutError,OSError,urllib.error.URLError):
        return None


class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,directory=str(STATIC),**kwargs)

    def _send_json(self, obj, status=200):
        body=json.dumps(obj,ensure_ascii=False,allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed=urlparse(self.path)
        if parsed.path=='/api/health':
            return self._send_json({'ok':True,'version':'1.2.0','ai_mode':'已配置 LLM 路由（实际调用失败会回退）' if os.getenv('OPENAI_API_KEY') else '离线路由，未接入 LLM',
                                   'data_cutoff':BASE['company']['data_cutoff']})
        if parsed.path=='/api/diagnosis':
            try:
                return self._send_json(build_diagnosis(mode_from(parse_qs(parsed.query))))
            except ValueError as e:
                return self._send_json({'error':str(e)},400)
        if parsed.path=='/':
            self.path='/index.html'
        if parsed.path.startswith('/api/'):
            return self._send_json({'error':'未知 API 路径'},404)
        return super().do_GET()

    def do_POST(self):
        parsed=urlparse(self.path)
        try:
            n=int(self.headers.get('Content-Length','0'))
        except ValueError:
            return self._send_json({'error':'Content-Length 无效'},400)
        if n < 1 or n>16000:
            return self._send_json({'error':'请求体为空或超过上限'},413)
        try:
            body=json.loads(self.rfile.read(n))
            if not isinstance(body,dict): raise ValueError('必须提供 JSON 对象')
            if parsed.path=='/api/pe':
                return self._send_json(scenario_pe(body.get('price')))
            if parsed.path=='/api/ask':
                mode=body.get('mode','normal')
                if mode not in ALLOWED: raise ValueError('未知模拟模式')
                q=body.get('question','')
                if not isinstance(q,str) or not q.strip() or len(q)>500: raise ValueError('请输入 1～500 字问题')
                ids=llm_route(q)
                return self._send_json(route_query(q,mode,chosen_ids=ids))
            return self._send_json({'error':'未知 API 路径'},404)
        except (ValueError,TypeError,UnicodeDecodeError,json.JSONDecodeError) as e:
            return self._send_json({'error':str(e)},400)

    def end_headers(self):
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; base-uri 'self'; object-src 'none'; frame-ancestors 'none'")
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('X-Content-Type-Options','nosniff')
        super().end_headers()


def serve():
    host=os.getenv('HOST','127.0.0.1')
    port=int(os.getenv('PORT','8000'))
    httpd=ThreadingHTTPServer((host,port),Handler)
    print(f'StockLens running at http://{host}:{httpd.server_port}  (Ctrl+C to stop)',flush=True)
    httpd.serve_forever()

if __name__=='__main__':
    serve()
