"""Approval-scope validation only; not a financial authority or acceptance issuer."""
import hashlib
import json
import re
import subprocess
from pathlib import Path

REPO=Path(r'D:\Work\Project Atlas')
ROOT=Path(__file__).parent
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()
def verify_sources(manifest,repo=REPO):
    for row in manifest['files']:
        file=repo/row['path']
        if not file.resolve().is_relative_to(repo.resolve()):raise ValueError('SOURCE_SCOPE_ESCAPE')
        if any(p.is_symlink() or p.is_junction() for p in [file,*file.parents]):raise ValueError('SOURCE_REPARSE_REFUSAL')
        raw=file.read_bytes()
        if len(raw)!=row['bytes'] or hashlib.sha256(raw).hexdigest()!=row['sha256']:raise ValueError('SOURCE_PIN_DRIFT')
def validate_scope(scope_sha256,approved_checkpoint):
    if not re.fullmatch('[0-9a-f]{64}',scope_sha256) or not re.fullmatch('[0-9a-f]{40}',approved_checkpoint):raise ValueError('EXACT_EXPLICIT_APPROVAL_ARGUMENTS_REQUIRED')
    proposal=json.loads((ROOT/'proposal.json').read_bytes())
    if hashlib.sha256(canonical(proposal)).hexdigest()!=scope_sha256:raise ValueError('APPROVED_SCOPE_HASH_MISMATCH')
    public=json.loads((REPO/proposal['public_scope_document']).read_bytes())
    if canonical(public)!=canonical(proposal):raise ValueError('PUBLIC_SCOPE_MISMATCH')
    if proposal.get('status')!='SOURCE_AND_DISPOSABLE_VALIDATED_READY_FOR_SEPARATE_AUTHORIZATION':raise ValueError('V3_NATIVE_VALIDATION_BLOCKED_NO_OPERATIONAL_ENTRY')
    if proposal['schema']!='QD_FINAL_INSTALLED_NONFINANCIAL_ACCEPTANCE_SCOPE_V3' or proposal['evidence_root']!=str(ROOT):raise ValueError('EXACT_EVIDENCE_ROOT_REQUIRED')
    if proposal['limits']!={'seconds':600,'entries':8192,'accounted_bytes':67108864}:raise ValueError('UNCHANGED_GLOBAL_LIMITS_REQUIRED')
    if proposal['application_release']!='2c039af29dfefd1df77e0caa3db3fdf5ed188118' or proposal['baseline']['revision']!=6 or proposal['baseline']['selected'] is not None:raise ValueError('EXACT_APPLICATION_AND_BASELINE_REQUIRED')
    if subprocess.check_output(['git','branch','--show-current'],cwd=REPO).decode().strip()!='chatgpt/atlas-rebuild-v1':raise ValueError('APPROVED_BRANCH_REQUIRED')
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO).decode().strip()!=approved_checkpoint:raise ValueError('APPROVED_CHECKPOINT_MISMATCH')
    subprocess.run(['git','merge-base','--is-ancestor',proposal['starting_checkpoint'],approved_checkpoint],cwd=REPO,check=True)
    raw=(ROOT/'source-manifest.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=proposal['source_manifest_sha256']:raise ValueError('SOURCE_MANIFEST_HASH_MISMATCH')
    verify_sources(json.loads(raw))
    return proposal
