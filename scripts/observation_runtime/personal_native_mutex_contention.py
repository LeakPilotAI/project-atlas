"""Native QD mutex contention diagnostic; never grants writer authority.

Requires an existing, independently verified control root. Does not write files.
"""
import json
import os
import subprocess
import sys

from scripts.observation_runtime.personal_existing_native_resource_evidence import inspect
from scripts.observation_runtime.personal_paper_inception import native_primitives

CHILD = '''import sys
from scripts.observation_runtime.personal_paper_inception import native_primitives
n=native_primitives()
with n.w.WindowsOutput(sys.argv[1]) as out:
    if n.native.file_identity(out.root_handle) != [int(x) for x in sys.argv[2].split(',')]:
        raise SystemExit('ROOT_ID_CHANGED')
    reg=n.native.Registry.__new__(n.native.Registry)
    reg.output=out
    reg.root_id=[int(x) for x in sys.argv[2].split(',')]
    reg._create_mutex()
    try:
        status=reg.wait(reg.mutex,200)
        print(status,flush=True)
        if status==0:reg.release(reg.mutex)
    finally:n.w.close_handle(reg.mutex)
'''


def probe(*, executable=sys.executable):
    evidence = inspect()
    if not evidence['all_six_verified']:
        raise ValueError('QD_NATIVE_RESOURCES_UNVERIFIED')
    control = evidence['resources']['control']
    native = native_primitives()
    with native.w.WindowsOutput(control['path']) as out:
        if native.native.file_identity(out.root_handle) != control['native_id']:
            raise ValueError('QD_CONTROL_IDENTITY_CHANGED')
        reg = native.native.Registry.__new__(native.native.Registry)
        reg.output, reg.root_id = out, control['native_id']
        reg._create_mutex()
        try:
            acquired = reg.wait(reg.mutex, 500)
            if acquired != 0:
                raise ValueError('QD_CONTROL_MUTEX_NOT_ACQUIRED')
            try:
                env = dict(os.environ)
                proc = subprocess.run([executable, '-B', '-c', CHILD, control['path'],
                                       ','.join(map(str, control['native_id']))],
                                      env=env, capture_output=True, text=True, timeout=20)
                blocked = proc.returncode == 0 and proc.stdout.strip() == '258'
            finally:
                if not reg.release(reg.mutex):
                    raise ValueError('QD_CONTROL_MUTEX_RELEASE_FAILED')
        finally:
            native.w.close_handle(reg.mutex)
    return {'schema': 'ATLAS_QD_NATIVE_MUTEX_CONTENTION_V1',
            'child_excluded_while_parent_holds': blocked,
            'writer_enrollment_accepted': False,
            'paper_start_authorized': False}


if __name__ == '__main__':
    result = probe()
    print(json.dumps(result, sort_keys=True))
    if not result['child_excluded_while_parent_holds']:
        raise SystemExit(1)
