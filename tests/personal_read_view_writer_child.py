"""Exact self-exiting native coordination competitor, synthetic roots only."""
import json
import os
import sys
from pathlib import Path
from threading import Timer

from scripts.observation_runtime.personal_coordination_store import NativePersonalCoordinationImages


def main():
    raw=sys.stdin.buffer.read(4097)
    if len(raw)>4096:raise ValueError('TEST_INPUT_CAPACITY')
    value=json.loads(raw);root=Path(value['root'])
    repo=Path(__file__).resolve().parents[1]
    if (root.parent.parent.parent!=repo/'logs/diagnostics'
            or not root.parent.parent.name.startswith('qd-read-view-')
            or any(p.is_symlink() or p.is_junction() for p in (root,*root.parents))):
        raise ValueError('EXACT_SYNTHETIC_ROOT_REQUIRED')
    images=NativePersonalCoordinationImages(root=str(root),native_root=value['native_root'],enrollment_digest=value['enrollment'])
    try:
        if value.get('abrupt_after_commit') is True:
            original=images.output.write_bound
            def abrupt(name,raw):
                binding=original(name,raw)
                if name=='0002-commit.json':os._exit(73)
                return binding
            images.output.write_bound=abrupt
        try:
            with images.transaction(readonly=False) as tx:
                before=tx.read();tx.publish(before,before)
            print(json.dumps({'published':True,'revision':images._load()[1]['revision']}))
        except ValueError as error:
            if str(error)!='PERSONAL_COORDINATION_WRITER_BUSY':raise
            print(json.dumps({'published':False,'reason':'WRITER_BUSY'}))
    finally:images.close()


if __name__=='__main__':
    watchdog=Timer(10,lambda:os._exit(72));watchdog.daemon=True;watchdog.start()
    try:main()
    finally:watchdog.cancel()
