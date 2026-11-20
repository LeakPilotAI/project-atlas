"""Exact disposable child exits at a requested publication boundary."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'backend'), str(ROOT/'tests')]
from continuation_fixture import Custody, manifests, records

from scripts.observation_runtime.offline_continuation import OfflineContinuation

root = Path(sys.argv[1])
archive = OfflineContinuation(root/'archive', custody=Custody(root), manifests=manifests())
if sys.argv[2] == 'partial_record':
    original_write = archive._write
    def interrupted_write(name, value):
        if name.endswith('-record.json'):
            from app.services.paper_financial_replay import body
            raw = body(value).encode()
            with (archive.root/name).open('xb') as stream:
                stream.write(raw[:len(raw)//2])
                stream.flush()
                os.fsync(stream.fileno())
                os._exit(73)
        return original_write(name, value)
    archive._write = interrupted_write
rows = records()
batch = {'QUALITY_DIPS': rows['QUALITY_DIPS'][:124], 'HYPERLIQUID': rows['HYPERLIQUID']}
def fault(phase):
    if phase == sys.argv[2]:
        os._exit(73)
archive.publish_committed_fixture_records('SYNTHETIC-BATCH-1', batch, fault=fault)
