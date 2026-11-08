"""Disposable, data-only isolated Chrome CDP candidate; never operational approval."""
import argparse
import http.server
import json
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from websockets.sync.client import connect
from scripts.observation_runtime.browser_equivalence_candidate import inspect_candidate

CHROME = Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe')


def probe(*, chrome=CHROME):
    if not chrome.is_file():
        raise ValueError('ISOLATED_CHROME_BINARY_REQUIRED')
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            payload = b'<html><title>ATLAS DISPOSABLE CDP</title><body>NO TRADING</body></html>'
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
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
        with tempfile.TemporaryDirectory(prefix='atlas-disposable-chrome-', ignore_cleanup_errors=True) as profile:
            process = subprocess.Popen([str(chrome), '--headless=new', '--no-first-run',
                '--no-default-browser-check', '--remote-debugging-port=0',
                '--remote-allow-origins=*', '--user-data-dir=' + profile, 'about:blank'],
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
                if 'NO TRADING' not in message.get('result', {}).get('result', {}).get('value', ''):
                    raise ValueError('ISOLATED_CHROME_RENDER_MISMATCH')
            print(json.dumps({'diagnostic': inspect_candidate(expected_url=url, observations=observations), 'observations': observations}), flush=True)
            return inspect_candidate(expected_url=url, observations=observations)
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


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--disposable-only', action='store_true', required=True)
    parser.parse_args()
    probe()
