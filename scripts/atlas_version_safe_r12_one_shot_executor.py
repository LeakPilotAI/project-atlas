"""One-shot nonfinancial r12 selector executor, isolated from frozen publisher.

Run using installed 2d487987 Python 3.12 -I -B -S. The exact source review,
operator's private one-shot SID-bound approval, application and support receipts
are required. NEVER start financial PAPER, connect provider accounts or order.

--inspect = read-only; --execute-reviewed-r12-code-only + exact confirmation
is an explicit nonfinancial native selector mutation, not PAPER commissioning.
"""
import argparse
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT=Path(r'D:\Work\Project Atlas')
APP=Path(r'D:\AtlasRuntime\releases\2d4879878bf58bea5a3ed0a986b809791f638fec')
PUBLISHER=ROOT/'scripts/atlas_version_safe_r12_selection_publisher.py'
PUBLISHER_PIN='69b6f4f30dc0a74378ac8853ca1150a434831306688e102420e6085a9c8da8a3'
SOURCE_REVIEW=ROOT/'docs/ATLAS_VERSION_SAFE_R12_CODE_PUBLISHER_SOURCE_REVIEW_R1_2026-11-09.json'
SOURCE_REVIEW_PIN='764f8f87880a1100f9b33274249daeadd147af704a604f371c131deee0f6a654'
PREDECESSOR='933482b46a31af43270a193a94a83353e945fbecc4eb4661e8b7f8e9c8262997'
PROPOSED='f4cf83bb1e98ecb7cfa3be37fe27e80a79b339dc26f73358a1702349b47958fd'
# Separately reviewed private exact-SID SHA pin. Until explicitly set, the
# executor refuses to use any local consent-looking file.
OPERATOR_APPROVAL_PIN='0024a5bf5bf933b039ceb9b52907bf88bdece812e6d4b883646cfbc17182833c'


def pinned(path,pin,limit=65536):
    if (not path.is_file() or path.is_symlink() or path.stat().st_size>limit
            or type(pin) is not str or not re.fullmatch('[0-9a-f]{64}',pin)):
        raise ValueError('ATLAS_R12_EXECUTOR_PINNED_FILE_REQUIRED')
    data=path.read_bytes()
    if hashlib.sha256(data).hexdigest()!=pin:
        raise ValueError('ATLAS_R12_EXECUTOR_FROZEN_SOURCE_CHANGED')
    return data


def load_publisher():
    if (not sys.flags.isolated or not sys.flags.no_site
            or not sys.flags.dont_write_bytecode or not sys.dont_write_bytecode
            or Path(sys.executable)!=APP/'python/python.exe'
            or Path(sys.base_prefix)!=APP/'python'):
        raise ValueError('ATLAS_R12_EXECUTOR_INSTALLED_PYTHON_REQUIRED')
    review=json.loads(pinned(SOURCE_REVIEW,SOURCE_REVIEW_PIN,limit=8192))
    if (review.get('schema')!='ATLAS_VERSION_SAFE_R12_CODE_ONLY_PUBLISHER_SOURCE_REVIEW_R1'
            or review.get('status')!='SOURCE_VERIFIED_NOT_SELECTION_APPROVAL'
            or review.get('publisher_source_sha256')!=PUBLISHER_PIN
            or review.get('selected_v7_head')!=PREDECESSOR
            or review.get('proposed_r12_head')!=PROPOSED
            or review.get('code_selection_operator_approval_pinned') is not False
            or review.get('native_r12_published') is not False
            or any(review.get(k) is not False for k in (
                'paper_accounts_authorized','providers_authorized',
                'simulated_orders_authorized','live_orders_authorized',
                'automatic_startup_authorized','live_trading_authorized'))):
        raise ValueError('ATLAS_R12_EXECUTOR_NONFINANCIAL_SOURCE_REVIEW_REQUIRED')
    pinned(PUBLISHER,PUBLISHER_PIN,limit=65536)
    spec=importlib.util.spec_from_file_location('atlas_r12_exact_reviewed_publisher',PUBLISHER)
    if spec is None or spec.loader is None:
        raise ValueError('ATLAS_R12_EXECUTOR_PUBLISHER_LOADER_REFUSED')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if (Path(module.__file__)!=PUBLISHER or module.APPROVAL_PIN is not None
            or module.R12_HEAD!=PROPOSED or module.V7_HEAD!=PREDECESSOR
            or module.APPROVAL.parent!=ROOT/'logs/diagnostics'):
        raise ValueError('ATLAS_R12_EXECUTOR_FROZEN_PUBLISHER_SCOPE_CHANGED')
    return module


def inspect():
    p=load_publisher()
    result=p.preview()
    if result.get('r12_published') is not False or result.get('financial_authority') is not False:
        raise ValueError('ATLAS_R12_EXECUTOR_NONFINANCIAL_READBACK_REQUIRED')
    return {**result,'private_exact_approval_pinned':type(OPERATOR_APPROVAL_PIN) is str,
            'execution_attempted':False}


def execute():
    p=load_publisher()
    if type(OPERATOR_APPROVAL_PIN) is not str or not re.fullmatch('[0-9a-f]{64}',OPERATOR_APPROVAL_PIN):
        raise ValueError('ATLAS_R12_EXECUTOR_SEPARATE_OPERATOR_APPROVAL_REQUIRED')
    p.APPROVAL_PIN=OPERATOR_APPROVAL_PIN
    p.installed_python()
    _,proposal=p.load_reviewed_plan()
    p.require_approved_operator(review=proposal)
    p.preview()  # refuse already published or altered native history before NTP
    return p.main(['--execute-one-shot-code-selection','--confirm-scope',p.SCOPE])


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    x=parser.add_mutually_exclusive_group(required=True)
    x.add_argument('--inspect',action='store_true',help='Read-only exact native proposal')
    x.add_argument('--execute-reviewed-r12-code-only',action='store_true',
                   help='One-shot native code selection; never PAPER financial activation')
    a=parser.parse_args(argv)
    return inspect() if a.inspect else execute()


if __name__=='__main__':
    print(json.dumps(main(),sort_keys=True),flush=True)
