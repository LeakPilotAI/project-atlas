"""Genuine retained test children only; no providers or financial stores."""
import hashlib
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import urlopen

from test_desktop_observation import m

ROOT=Path(__file__).resolve().parents[1]


def launch():
 env={**os.environ,'PYTHONPATH':str(ROOT/'backend/.venv/Lib/site-packages')+os.pathsep+str(ROOT/'backend'),'PYTHONDONTWRITEBYTECODE':'1'}
 child=subprocess.Popen([sys._base_executable,'-B','scripts/observation_runtime/desktop_observation.py','--disposable-test'],cwd=ROOT,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
 try:
  with ThreadPoolExecutor(1) as reader:
   ready=json.loads(reader.submit(child.stdout.readline).result(timeout=15))
  assert ready['pid']==child.pid and ready['data_only_seconds']==0 and ready['creation_filetime']>0
  response=json.load(urlopen(ready['url']+'health',timeout=3))
  assert response['host_id']==ready['host_id'] and response['financial_writers'] is False
  roots=[p for p in (ROOT/'logs/observation-only').glob('session-test-*') if (p/'host-ready.json').exists() and json.loads((p/'host-ready.json').read_text())['host_id']==ready['host_id']]
  assert len(roots)==1
  return child,ready,roots[0]
 except BaseException:
  if child.poll() is None:child.kill();child.wait(timeout=5)
  raise


def archive(root):
 reader=m.Session.__new__(m.Session);reader.root=root;reader.test=True
 return reader.history()['sessions'][0]


def test_three_actual_host_close_reopen_cycles_preserve_prior_evidence():
 previous=[]
 for _ in range(3):
  child,ready,root=launch()
  try:
   for old,checksum in previous:assert hashlib.sha256(old.read_bytes()).hexdigest()==checksum
   before=(root/'observations.jsonl').read_bytes()
   for route in ['api/observation/history','api/observation/diagnostics','api/investments/quality-dips/selected-paper']:
    assert urlopen(ready['url']+route,timeout=3).status==200
   assert (root/'observations.jsonl').read_bytes()==before
   child.stdin.close();assert child.wait(timeout=12)==0
   rows=archive(root);assert rows['status']=='CLOSED' and rows['records'][-1]['kind']=='SESSION_STOP'
   p=root/'observations.jsonl';previous.append((p,hashlib.sha256(p.read_bytes()).hexdigest()))
  finally:
   if child.poll() is None:child.kill();child.wait(timeout=5)


def test_actual_child_crash_never_creates_graceful_stop_and_partial_append_refuses():
 child,_ready,root=launch()
 child.kill();child.wait(timeout=5)  # Exact retained disposable child, never process-name termination.
 rows=archive(root);assert rows['status']=='ACTIVE_OR_INTERRUPTED' and all(r['kind']!='SESSION_STOP' for r in rows['records'])
 p=root/'observations.jsonl';original=p.read_bytes()
 with p.open('ab') as stream:stream.write(b'{"interrupted":')
 import pytest
 with pytest.raises(ValueError,match='INTERRUPTED_APPEND'):archive(root)
 assert p.read_bytes()==original+b'{"interrupted":'
