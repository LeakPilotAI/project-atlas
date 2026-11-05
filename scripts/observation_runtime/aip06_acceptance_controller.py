"""Pinned candidate entry. Refuses unresolved native execution before effects.

The control-plane logic is injectable and source-qualified separately. Native
authorization, observer and fault/load/async bindings remain unavailable. This
entry cannot fall back to subprocess, unguarded APIs or injected qualification.
"""

import argparse
import ntpath
from pathlib import Path

from scripts.observation_runtime.aip06_acceptance_plan import REPO, decode_plan, require_execution_ready
from scripts.observation_runtime.aip06_harness import need


def prepare(raw, sha256):
    return decode_plan(raw,sha256)


def control_plane(raw, sha256, *, clock_ns, files, owner, dispatcher_factory):
    """Construct only; no native loader, grant, preflight query or execution."""
    from scripts.observation_runtime.aip06_acceptance_control import OuterOwner
    return OuterOwner(raw, sha256, clock_ns=clock_ns, files=files, owner=owner,
                      dispatcher_factory=dispatcher_factory)


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--role',required=True,choices=('outer-owner','controller'))
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--manifest-sha256',required=True)
    args=parser.parse_args(argv)
    expected=ntpath.join(REPO,'docs','AIP_06_NATIVE_CANDIDATE_RUN_MANIFEST_2026-11-05.json')
    need(args.manifest==expected,'EXACT_REVIEWED_CANDIDATE_MANIFEST_PATH')
    path=Path(args.manifest)
    with path.open('rb') as source:raw=source.read(1024**2+1)
    value=prepare(raw,args.manifest_sha256)
    require_execution_ready(value)


if __name__=='__main__':
    main()
