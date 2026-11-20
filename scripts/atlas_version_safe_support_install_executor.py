"""One-shot reviewed NTP support-install invocation, with NO financial/selector powers.

A separate private exact decision + current Windows SID must match. Historical
bootstrap/source review and installed Python are immutable and independently pinned.
Do not invoke live install through tests; use --inspect for safe read-only check.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT=Path(r'D:\Work\Project Atlas')
APP=Path(r'D:\AtlasRuntime\releases\2d4879878bf58bea5a3ed0a986b809791f638fec')
BOOTSTRAP=ROOT/'scripts/atlas_version_safe_support_bootstrap.py'
REVIEW=ROOT/'docs/ATLAS_VERSION_SAFE_SUPPORT_BOOTSTRAP_SOURCE_REVIEW_R1_2026-11-09.json'
BOOTSTRAP_SHA='995958f4b6fd8f132f8ccb24a869e2ea0d676fbe5f836f0b2a2094600430d90d'
REVIEW_SHA='e58cc6eaecf276ab69f6f4a5c793f65d4f2c1eb02ce5481ca57ca13b209e4766'
SUPPORT_MANIFEST='d61fd6c9fa18bd819f3328040e6c40581efc8faeef8eca8e6326eb110b919ad8'
APP_RECEIPT='acdae2f01fb5defdf0e302240dc589eca0f1c99e3fcc15ec319d98260125cbb6'
# Separate private one-shot operator decision; no user SID in source or Git.
# Not pinned until explicit approval is create-only recorded and checked.
APPROVAL_PIN = 'a3c669d1b4003e1c748b0225cec3b920513f1019a1eb6a113e661783e2c95029'


def pinned_bytes(path,digest,*,limit=262144):
    if not path.is_file() or path.is_symlink() or path.stat().st_size>limit:
        raise ValueError('ATLAS_SUPPORT_EXECUTOR_REVIEWED_SOURCE_REQUIRED')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=digest:
        raise ValueError('ATLAS_SUPPORT_EXECUTOR_REVIEWED_SOURCE_PIN_CHANGED')
    return raw


def load_bootstrap():
    if (not sys.flags.isolated or not sys.flags.no_site
            or not sys.flags.dont_write_bytecode or not sys.dont_write_bytecode
            or Path(sys.executable)!=APP/'python/python.exe'):
        raise ValueError('ATLAS_SUPPORT_EXECUTOR_INSTALLED_PYTHON_ONLY')
    raw=pinned_bytes(REVIEW,REVIEW_SHA,limit=4096)
    review=json.loads(raw)
    if (review.get('schema')!='ATLAS_VERSION_SAFE_SUPPORT_BOOTSTRAP_SOURCE_REVIEW_R1'
            or review.get('status')!='SOURCE_VERIFIED_NOT_OPERATOR_PERMISSION'
            or review.get('bootstrap_normalized_sha256')!=BOOTSTRAP_SHA
            or review.get('support_manifest_sha256')!=SUPPORT_MANIFEST
            or review.get('application_receipt_sha256')!=APP_RECEIPT
            or any(review.get(k) is not False for k in (
                'support_install_authorized','release_selection_authorized',
                'financial_accounts_authorized','providers_authorized',
                'simulated_orders_authorized','live_orders_authorized'))):
        raise ValueError('ATLAS_SUPPORT_EXECUTOR_NOT_APPROVAL_FROM_SOURCE_REVIEW')
    if not BOOTSTRAP.is_file() or BOOTSTRAP.is_symlink() or BOOTSTRAP.stat().st_size>65536:
        raise ValueError('ATLAS_SUPPORT_EXECUTOR_BOOTSTRAP_SOURCE_REQUIRED')
    code=BOOTSTRAP.read_bytes().replace(b'\r\n',b'\n')
    if hashlib.sha256(code).hexdigest()!=BOOTSTRAP_SHA:
        raise ValueError('ATLAS_SUPPORT_EXECUTOR_FROZEN_BOOTSTRAP_CHANGED')
    spec=importlib.util.spec_from_file_location('atlas_version_safe_support_reviewed',BOOTSTRAP)
    if spec is None or spec.loader is None:
        raise ValueError('ATLAS_SUPPORT_EXECUTOR_BOOTSTRAP_LOAD_REFUSED')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if (Path(module.__file__)!=BOOTSTRAP
            or module.MANIFEST_SHA!=SUPPORT_MANIFEST
            or module.APP_SHA!=APP_RECEIPT
            or module.APPROVAL_PIN is not None):
        raise ValueError('ATLAS_SUPPORT_EXECUTOR_FROZEN_ADMISSION_CHANGED')
    return module


def inspect():
    module=load_bootstrap()
    result=module.main(['--inspect'])
    if (result.get('status')!='VERSION_SAFE_NTP_SUPPORT_NATIVE_BOOTSTRAP_REVIEW_PASS'
            or result.get('native_support_installed') is not False
            or result.get('financial_authority') is not False
            or result.get('selected') is not False):
        raise ValueError('ATLAS_SUPPORT_EXECUTOR_REVIEW_NOT_SAFE')
    result['execution_approved']=type(APPROVAL_PIN) is str
    return result


def execute():
    module=load_bootstrap()
    if type(APPROVAL_PIN) is not str or len(APPROVAL_PIN)!=64:
        raise ValueError('ATLAS_SUPPORT_EXECUTOR_ONE_SHOT_PRIVATE_APPROVAL_NOT_PINNED')
    module.APPROVAL_PIN=APPROVAL_PIN
    # Isolated -I -B -S starts with no third-party/module paths. Prepare only
    # paths within the immutable installed app BEFORE checking native SID.
    module.require_installed_interpreter()
    module.require_install_approval()
    # Physical destination/control must be absent BEFORE opening public NTP.
    module.inspect()
    # Frozen bootstrap CLI mistakenly falls through into --inspect after a
    # successful copy. Invoke the exact reviewed approval-gated function once
    # instead, without changing any hash-pinned bootstrap source bytes.
    return module.install_code_only()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--inspect',action='store_true')
    group.add_argument('--execute-one-shot-nonfinancial-support',action='store_true')
    a=parser.parse_args(argv)
    return inspect() if a.inspect else execute()


if __name__=='__main__':
    print(json.dumps(main(),sort_keys=True),flush=True)
