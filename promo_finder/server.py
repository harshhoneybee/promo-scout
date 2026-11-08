"""Loopback-only prototype. No persistence, public hosting, cookies or API keys in browser."""
import base64
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from .engine import run
from .parser import parse_zip_bytes, parse_episode
from .providers import ChatProvider

ROOT = Path(__file__).resolve().parent.parent
MAX_BODY = 15_000_000


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Uploaded filenames, scripts and credentials do not go into access logs.

    def respond(self,status,data,content_type='application/json'):
        body = data if isinstance(data,bytes) else json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def allowed(self):
        expected = {f'localhost:{self.server.server_port}',f'127.0.0.1:{self.server.server_port}'}
        if self.headers.get('Host','') not in expected:
            return False
        origin = self.headers.get('Origin')
        return not origin or urlparse(origin).netloc in expected and urlparse(origin).scheme=='http'

    def do_GET(self):
        if not self.allowed():
            self.respond(403,{'error':'Local browser access only'})
        elif self.path=='/':
            self.respond(200,(ROOT/'web'/'index.html').read_bytes(),'text/html; charset=utf-8')
        elif self.path=='/api/config':
            try:
                provider = ChatProvider.from_env()
                result = {'ai_configured':True,'model':provider.model}
            except ValueError:
                result = {'ai_configured':False,'model':''}
            self.respond(200,result)
        else:
            self.respond(404,{'error':'Not found'})

    def do_POST(self):
        if not self.allowed():
            self.respond(403,{'error':'Local browser access only'})
            return
        if self.path!='/api/analyze':
            self.respond(404,{'error':'Not found'})
            return
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':
            self.respond(415,{'error':'Expected application/json'})
            return
        try:
            length = int(self.headers.get('Content-Length',0))
            if not 0<length<=MAX_BODY:
                raise ValueError('Request must be 1 byte to 15 MB')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data,dict):
                raise ValueError('Expected JSON object')
            if data.get('demo') is True:
                ep = ROOT/'examples'/'demo_episode.txt'
                episodes = [parse_episode(ep.read_text(),ep.name)]
            else:
                blob = base64.b64decode(data.get('data',''),validate=True)
                filename = Path(data.get('filename','')).name
                if filename.lower().endswith('.zip'):
                    episodes = parse_zip_bytes(blob)
                elif filename.lower().endswith('.txt') and len(blob)<=1_000_000:
                    episodes = [parse_episode(blob.decode('utf-8-sig'),filename)]
                else:
                    raise ValueError('Upload a ZIP or a TXT file (TXT max 1 MB)')
            mode = data.get('mode','baseline')
            provider = ChatProvider.from_env() if mode=='ai' else None
            result = run(episodes,mode,data.get('top_k',10),provider)
            self.respond(200,result)
        except (ValueError,TypeError,KeyError,UnicodeError) as exc:
            self.respond(400,{'error':str(exc)})
        except Exception:
            self.respond(500,{'error':'Analysis failed. Check input format and provider configuration.'})


def serve(port=8765):
    server = ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.daemon_threads = True
    print(f'Promo Scout running at http://localhost:{port} — Ctrl+C to stop',flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
