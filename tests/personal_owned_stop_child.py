"""Self-exiting, synthetic-only native timing worker; never operational launch."""
import json
import os
from pathlib import Path

from test_personal_native_pipeline_capacity import run_native_pipeline

from scripts.observation_runtime.quality_dips_read_service import observe_self
from scripts.observation_runtime import aip06_fixture_guard as guarded


def main():
    guard = guarded.require_fixture('owned-stop-child')
    root=Path(os.environ['ATLAS_PERSONAL_PIPELINE_TEST_ROOT'])
    repo=Path(__file__).resolve().parents[1]
    if root.parent!=repo/'logs/diagnostics' or not root.name.startswith('qd-personal-pipeline-owned-'):
        raise ValueError('CONFINED_SYNTHETIC_TIMING_ROOT_REQUIRED')
    if root.exists():raise ValueError('NO_EXISTING_ACCOUNT_ADOPTION')
    guarded.mkdir(root)
    account=root/'account';guarded.mkdir(account)
    nonce=os.environ['ATLAS_SYNTHETIC_STOP_NONCE']
    identity=observe_self()
    def observe(phase,value):
        print(json.dumps({'timing_channel':nonce,'phase':phase,'identity':identity,'value':value}),flush=True)
        if phase=='READY':
            raw=guard.read_input(maximum_bytes=1024, timeout=8, line=True)
            command=json.loads(raw)
            guard.verify_received_stop(command, nonce, identity)
    run_native_pipeline(account,stop_observer=observe)


if __name__=='__main__':
    with guarded.watchdog(seconds=120,exit_code=71):
        main()
