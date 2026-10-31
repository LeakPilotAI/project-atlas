"""Installed Chrome acceptance for an already running, confined synthetic host."""
import argparse
import html
import json
import re
import subprocess
import uuid
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]

def main():
 parser=argparse.ArgumentParser();parser.add_argument('root',type=Path);parser.add_argument('--width',type=int,default=1440);args=parser.parse_args()
 root=args.root.absolute()
 if (root.parent!=ROOT/'logs/diagnostics' or not root.name.startswith('qd-research-browser-')
     or any(p.is_symlink() or p.is_junction() for p in (root,*root.parents)) or args.width not in (800,1440)):
  raise ValueError('CONFINED_BROWSER_TEST_ROOT_AND_WIDTH_REQUIRED')
 ready=json.loads((root/'ready.json').read_text());url=ready['url'];parts=urlsplit(url)
 if parts.scheme!='http' or parts.hostname!='127.0.0.1' or parts.path!='/quality_dips.html' or ready['mode']!='DISPOSABLE_SYNTHETIC_ONLY':raise ValueError('EXACT_DISPOSABLE_HOST_REQUIRED')
 with urlopen(f'http://127.0.0.1:{parts.port}/health',timeout=3) as response:health=json.load(response)
 if health['host_id']!=ready['host_id'] or health['financial_writers'] is not False:raise ValueError('HOST_IDENTITY_REQUIRED')
 chrome=Path('C:/Program Files/Google/Chrome/Application/chrome.exe')
 if not chrome.is_file():raise RuntimeError('INSTALLED_CHROME_NOT_AVAILABLE')
 label='chrome-'+str(args.width)+'-'+uuid.uuid4().hex
 command=[str(chrome),'--headless=new','--disable-background-networking','--disable-sync','--no-first-run','--no-default-browser-check','--disable-extensions','--disable-component-update','--user-data-dir='+str(root/(label+'-profile')),'--window-size='+str(args.width)+',1000','--virtual-time-budget=7000','--dump-dom','--screenshot='+str(root/(label+'.png')),url+'?acceptance=1']
 run=subprocess.run(command,capture_output=True,check=False,timeout=45)
 (root/(label+'.html')).write_bytes(run.stdout);(root/(label+'-stderr.txt')).write_bytes(run.stderr)
 match=re.search(r'<pre id="browser-acceptance-result"[^>]*>(.*?)</pre>',run.stdout.decode('utf8'),re.DOTALL)
 if not match:raise AssertionError('BROWSER_RESULT_MISSING; retain stdout/stderr')
 result=json.loads(html.unescape(match.group(1)))
 rows=[json.loads(line) for line in (root/'http.jsonl').read_text().splitlines()]
 result['http_statuses']=[row for row in rows if row['path']=='/api/observation/quality-dips']
 result['legacy_research_requests']=[row for row in rows if row['path'].startswith('/api/investments/quality-dips?')]
 result['process_returncode']=run.returncode
 (root/(label+'-result.json')).write_text(json.dumps(result,indent=2))
 assert run.returncode==0 and result['passed'] and not result['legacy_research_requests'],result
 assert any(row['status']==503 for row in result['http_statuses']),result
 assert result['viewport']['bodyWidth']<=result['viewport']['width'],result
 print(json.dumps(result))

if __name__=='__main__':main()
