"""Self-exiting confined test child;never an operational process."""
import os
import sys
import threading
from pathlib import Path

sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[1]/'backend')]
from app.services.paper_financial_replay import body
from native_continuation_v2_fixture import Suite
from native_continuation_v2_owned import self_identity

path,mode,phase=sys.argv[1:]
threading.Timer(55,lambda:os._exit(74)).start()
s=Suite(path)
try:
    if mode=='switch':
        s.switch.switch(fault=lambda stage:os._exit(73) if stage==phase else None)
        print('ACKNOWLEDGED',flush=True)
    elif mode=='inspect':print(body(s.switch.inspect()),flush=True)
    elif mode=='hold':
        for journal in s.j.values():journal.read()
        print(body(self_identity()),flush=True)
        sys.stdin.readline()
finally:s.close()
os._exit(0)
