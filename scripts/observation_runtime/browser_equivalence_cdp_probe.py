"""Disposable, data-only isolated Chrome CDP candidate; never operational approval."""
import argparse
import http.server
import hashlib
import json
import subprocess
import tempfile
import time
import urllib.request
import urllib.error
from pathlib import Path

from websockets.sync.client import connect
from scripts.observation_runtime.browser_equivalence_candidate import inspect_candidate

CHROME = Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe')


def probe(*, chrome=CHROME, installed_static_preview=None):
    if not chrome.is_file():
        raise ValueError('ISOLATED_CHROME_BINARY_REQUIRED')
    static_bytes = None
    static_digest = None
    if installed_static_preview is not None:
        static_path = Path(installed_static_preview)
        release_root = Path(r'D:\AtlasRuntime\releases').resolve()
        resolved = static_path.resolve()
        if (len(resolved.parents) < 6 or resolved.parents[4] != release_root
                or resolved.parent.name != 'static' or resolved.parents[1].name != 'app'
                or resolved.parents[2].name != 'backend'):
            raise ValueError('INSTALLED_RELEASE_ROOT_REQUIRED')
        if (static_path.is_symlink() or not static_path.is_file()
                or static_path.name != 'dashboard.html'
                or static_path.stat().st_size > 2_000_000):
            raise ValueError('INSTALLED_STATIC_DASHBOARD_REQUIRED')
        static_bytes = static_path.read_bytes()
        static_digest = hashlib.sha256(static_bytes).hexdigest()
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != '/':
                self.send_error(404, 'DISPOSABLE_PREVIEW_ROOT_ONLY')
                return
            payload = static_bytes if static_bytes is not None else b'<html><title>ATLAS DISPOSABLE CDP</title><body>NO TRADING</body></html>'
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'")
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        def log_message(self, *_):
            pass
    from http.server import ThreadingHTTPServer
    from threading import Thread
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f'http://127.0.0.1:{server.server_port}/'
    process = None
    try:
        with urllib.request.urlopen(url, timeout=3) as preview_response:
            csp = preview_response.headers.get('Content-Security-Policy', '')
            if "default-src 'none'" not in csp:
                raise ValueError('DISPOSABLE_PREVIEW_CSP_REQUIRED')
        try:
            urllib.request.urlopen(url + 'api/financial', timeout=3)
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise ValueError('DISPOSABLE_PREVIEW_ROUTE_NOT_REFUSED') from error
        else:
            raise ValueError('DISPOSABLE_PREVIEW_ROUTE_NOT_REFUSED')
        with tempfile.TemporaryDirectory(prefix='atlas-disposable-chrome-', ignore_cleanup_errors=True) as profile:
            process = subprocess.Popen([str(chrome), '--headless=new', '--no-first-run',
                '--no-default-browser-check', '--remote-debugging-port=0',
                '--user-data-dir=' + profile, 'about:blank'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            port_file = Path(profile) / 'DevToolsActivePort'
            deadline = time.monotonic() + 12
            while not port_file.is_file() and time.monotonic() < deadline:
                if process.poll() is not None:
                    raise ValueError('ISOLATED_CHROME_EXITED')
                time.sleep(.1)
            if not port_file.is_file():
                raise ValueError('ISOLATED_CHROME_CDP_TIMEOUT')
            port = int(port_file.read_text().splitlines()[0])
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list', timeout=3) as response:
                targets = json.load(response)
            tabs = [t for t in targets if t.get('type') == 'page' and t.get('webSocketDebuggerUrl')]
            if len(tabs) != 1:
                raise ValueError('ISOLATED_CHROME_EXACT_TAB_REQUIRED')
            target = tabs[0]
            observations = []
            with connect(target['webSocketDebuggerUrl'], open_timeout=3, max_size=1048576) as ws:
                ws.send(json.dumps({'id': 1, 'method': 'Page.navigate', 'params': {'url': url}}))
                while True:
                    message = json.loads(ws.recv(timeout=5))
                    if message.get('id') == 1:
                        if 'error' in message or message.get('result', {}).get('errorText'):
                            raise ValueError('ISOLATED_CHROME_NAVIGATION_FAILED')
                        break
                for stage in ('created', 'navigated', 'rendered'):
                    time.sleep(.02)
                    ws.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': 'location.href'}}))
                    while True:
                        message = json.loads(ws.recv(timeout=5))
                        if message.get('id') == 2:
                            break
                    actual = message.get('result', {}).get('result', {}).get('value')
                    if actual != url:
                        raise ValueError('ISOLATED_CHROME_ORIGIN_NOT_READY:' + repr(actual))
                    observations.append({'stage': stage, 'target_id': target['id'], 'url': actual, 'observed_ns': time.monotonic_ns(), 'error': None})
                ws.send(json.dumps({'id': 3, 'method': 'Runtime.evaluate', 'params': {'expression': 'document.body.innerText'}}))
                while True:
                    message = json.loads(ws.recv(timeout=5))
                    if message.get('id') == 3:
                        break
                rendered_text = message.get('result', {}).get('result', {}).get('value', '')
                if static_bytes is not None:
                    ws.send(json.dumps({'id': 4, 'method': 'Runtime.evaluate',
                        'params': {'expression': 'JSON.stringify({title:document.title,ready:document.readyState,body:document.body!==null})'}}))
                    while True:
                        document_message = json.loads(ws.recv(timeout=5))
                        if document_message.get('id') == 4:
                            break
                    document = json.loads(document_message.get('result', {}).get('result', {}).get('value', '{}'))
                    if document.get('ready') != 'complete':
                        time.sleep(.5)
                        ws.send(json.dumps({'id': 5, 'method': 'Runtime.evaluate', 'params': {'expression': 'document.readyState'}}))
                        while True:
                            state_message = json.loads(ws.recv(timeout=5))
                            if state_message.get('id') == 5:
                                break
                        document['ready'] = state_message.get('result', {}).get('result', {}).get('value')
                    if document.get('title') != 'Atlas Command' or document.get('ready') != 'complete' or document.get('body') is not True:
                        raise ValueError('INSTALLED_STATIC_DOM_NOT_RENDERED')
                if static_bytes is None and 'NO TRADING' not in rendered_text:
                    raise ValueError('ISOLATED_CHROME_RENDER_MISMATCH')
            result = inspect_candidate(expected_url=url, observations=observations)
            evidence = {'diagnostic': result, 'observations': observations, 'installed_static_preview_sha256': static_digest, 'operational_dashboard_verified': False, 'preview_csp_enforced': True, 'non_root_route_refused': True, 'installed_static_dom_rendered': static_bytes is not None}
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        if thread.is_alive() or server.fileno() != -1 or (process is not None and process.poll() is None):
            raise RuntimeError('ISOLATED_BROWSER_CLEANUP_UNVERIFIED')
    evidence['cleanup'] = {'chrome_parent_exited': True, 'server_thread_exited': True, 'server_socket_closed': True}
    print(json.dumps(evidence), flush=True)
    return evidence


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--disposable-only', action='store_true', required=True)
    parser.add_argument('--installed-static-preview', type=Path)
    args = parser.parse_args()
    probe(installed_static_preview=args.installed_static_preview)
