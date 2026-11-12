"""仅供本机浏览器禁止file://时的HTTP预览；不改浏览器安全策略。"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import mimetypes
from pathlib import Path
import threading
from urllib.parse import unquote, urlparse


def enable(roots, browser):
    from playwright.sync_api import BrowserType, Page
    allowed = [Path(r).resolve() for r in roots]
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = Path(unquote(urlparse(self.path).path)).resolve()
            if not path.is_file() or not any(path.is_relative_to(r) for r in allowed):
                self.send_error(404); return
            data = path.read_bytes()
            if path.suffix in ('.html', '.css'):
                data = data.replace(b'file://', base.encode())
            self.send_response(200)
            self.send_header('Content-Type', mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
            self.end_headers(); self.wfile.write(data)
        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    base = f'http://127.0.0.1:{server.server_address[1]}'
    threading.Thread(target=server.serve_forever, daemon=True).start()
    launch, goto = BrowserType.launch, Page.goto
    def local_launch(self, *args, **kw):
        if not kw.get('executable_path') or not Path(kw['executable_path']).exists():
            kw['executable_path'] = browser
        return launch(self, *args, **kw)
    def local_goto(self, url, *args, **kw):
        if url.startswith('file://'):
            url = base + url[7:]
        return goto(self, url, *args, **kw)
    BrowserType.launch, Page.goto = local_launch, local_goto
    return server
