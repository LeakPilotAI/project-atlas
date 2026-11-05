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


def inherited_prepare():
    """Use private input after the existing child bootstrap installed its guard.

    Reading the repository manifest through Path.open inside the child guard
    is deliberately avoided. The input carries exact canonical bytes whose
    hash must match the predeclared logical argv and inherited source pins.
    """
    from app.services.paper_financial_replay import strict
    from scripts.observation_runtime.aip06_controller_contract import inherited_context
    from scripts.observation_runtime.aip06_fixture_guard import require_fixture
    guard = require_fixture('inherited-acceptance-controller')
    services = guard.processes
    descriptor = services.runtime.descriptor
    raw = guard.read_input(maximum_bytes=65536, timeout=6)
    return inherited_context(guard, descriptor, strict(raw.decode('utf-8')))


def publish_prepared(context):
    from scripts.observation_runtime.aip06_controller_contract import ControllerContext
    need(type(context) is ControllerContext, 'TYPED_CONTROLLER_PREPARATION_CONTEXT')
    context.guard.check()
    context.guard.processes.emit_output({'schema':'AIP06_CONTROLLER_PREPARED_V1',
        'manifest':context.intent.sha256,'owner':context.guard.owner,'root_owner':context.root_owner,
        'native_acceptance':False})


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--role',required=True,choices=('outer-owner','controller'))
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--manifest-sha256',required=True)
    args=parser.parse_args(argv)
    expected=ntpath.join(REPO,'docs','AIP_06_NATIVE_CANDIDATE_RUN_MANIFEST_2026-11-05.json')
    need(args.manifest==expected,'EXACT_REVIEWED_CANDIDATE_MANIFEST_PATH')
    if args.role == 'controller':
        context = inherited_prepare()
        need(args.manifest_sha256 == context.intent.sha256, 'CONTROLLER_ARGPARSE_INTENT_CONFLICT')
        # This entry performs PREPARE only and exits. It cannot dispatch a native
        # matrix. Native execution remains behind the separate closed gate.
        publish_prepared(context)
        return
    path=Path(args.manifest)
    with path.open('rb') as source:raw=source.read(1024**2+1)
    value=prepare(raw,args.manifest_sha256)
    require_execution_ready(value)


if __name__=='__main__':
    main()
