"""Self-exiting, synthetic-only native timing worker; never operational launch."""
import json
import os
import sys
from pathlib import Path
from threading import Timer

from test_personal_native_pipeline_capacity import run_native_pipeline

from scripts.observation_runtime.quality_dips_read_service import observe_self


def main():
    root=Path(os.environ['ATLAS_PERSONAL_PIPELINE_TEST_ROOT'])
    repo=Path(__file__).resolve().parents[1]
    if root.parent!=repo/'logs/diagnostics' or not root.name.startswith('qd-personal-pipeline-owned-'):
        raise ValueError('CONFINED_SYNTHETIC_TIMING_ROOT_REQUIRED')
    if root.exists():raise ValueError('NO_EXISTING_ACCOUNT_ADOPTION')
    root.mkdir()
    account=root/'account';account.mkdir()
    nonce=os.environ['ATLAS_SYNTHETIC_STOP_NONCE']
    identity=observe_self()
    def observe(phase,value):
        print(json.dumps({'timing_channel':nonce,'phase':phase,'identity':identity,'value':value}),flush=True)
        if phase=='READY':
            raw=sys.stdin.readline(1025)
            command=json.loads(raw)
            if command!={'action':'STOP','nonce':nonce,'identity':identity}:
                raise ValueError('EXACT_OWNED_SYNTHETIC_STOP_REQUIRED')
    run_native_pipeline(account,stop_observer=observe)


if __name__=='__main__':
    watchdog=Timer(120,lambda:os._exit(71));watchdog.daemon=True;watchdog.start()
    try:main()
    finally:watchdog.cancel()
