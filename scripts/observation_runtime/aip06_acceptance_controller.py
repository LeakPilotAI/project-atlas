"""Pinned candidate entry. Refuses unresolved native execution before effects.

The manifest/parser and exact command are concrete; outer-owner native binding
and independent grader are explicitly absent. This must not masquerade as a
complete native controller or fall back to subprocess, unguarded APIs or mocks.
"""

import argparse
import ntpath
from pathlib import Path

from scripts.observation_runtime.aip06_acceptance_plan import REPO, decode_plan, require_execution_ready
from scripts.observation_runtime.aip06_harness import need


def prepare(raw, sha256):
    return decode_plan(raw,sha256)


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
