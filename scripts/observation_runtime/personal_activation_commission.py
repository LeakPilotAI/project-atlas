"""Explicit one-shot native PAPER activation entrypoint; no default authorization.

The caller must supply an existing complete operator-signed-in-session record,
release digest, account bindings and the exact installed clock source. Nothing
is inferred from commissioning scope or diagnostic data.
"""
import argparse
import json
import ntpath
from pathlib import Path

from scripts.observation_runtime.personal_activation_publisher import publish_personal_activation
from scripts.observation_runtime.personal_windows_clock import LocalWindowsClock
from scripts.volume_inspector.windows_output import current_sid


def commission(*, root, record_path, policy_path, release_digest, accounts_path,
               expected_clock_source, runtime_id):
    if not all(type(v) is str and v for v in (root, record_path, policy_path,
                                              release_digest, accounts_path,
                                              expected_clock_source, runtime_id)):
        raise ValueError('EXPLICIT_ACTIVATION_INPUTS_REQUIRED')
    if len(release_digest) != 64 or any(c not in '0123456789abcdef' for c in release_digest):
        raise ValueError('EXPLICIT_RELEASE_DIGEST_REQUIRED')
    if (ntpath.normpath(root) != root
            or not ntpath.normcase(root).startswith('d:\\atlascustody\\personalpaper\\')
            or any(c in root[3:] for c in (':', '%', '\x00', '/'))
            or any(part in ('', '.', '..') for part in root[3:].split('\\'))):
        raise ValueError('EXPLICIT_NATIVE_ACTIVATION_ROOT_REQUIRED')
    record = json.loads(Path(record_path).read_text(encoding='utf-8'))
    policy = json.loads(Path(policy_path).read_text(encoding='utf-8'))
    accounts = json.loads(Path(accounts_path).read_text(encoding='utf-8'))
    if (type(record) is not dict or type(accounts) is not dict
            or set(accounts) != {'HYPERLIQUID', 'QUALITY_DIPS'}
            or any(type(v) is not str or len(v) != 64
                   or any(c not in '0123456789abcdef' for c in v)
                   for v in accounts.values())
            or record.get('accounts') != accounts
            or record.get('release_digest') != release_digest):
        raise ValueError('ACTIVATION_ACCOUNTS_OR_RELEASE_MISMATCH')
    # Check the full static activation contract before acquiring a short-lived
    # trusted-clock capability or entering native create-only custody.
    from app.services.personal_paper_runtime import validate_policy
    from app.services.paper_financial_replay import digest
    validated_policy = validate_policy(policy)
    if (record.get('policy_digest') != digest(validated_policy)
            or record.get('origin') != 'LOCAL_OPERATOR'
            or record.get('schema') != 'ATLAS_PERSONAL_ACTIVATION_V1'
            or not isinstance(record.get('actions'), list)
            or not record['actions']):
        raise ValueError('ACTIVATION_POLICY_OR_ACTION_BINDING_REQUIRED')
    clock = LocalWindowsClock(expected_source=expected_clock_source, runtime_id=runtime_id)
    try:
        return publish_personal_activation(root=root, record=record, policy=policy,
            operator_id=current_sid(), release_digest=release_digest,
            accounts=accounts, clock=clock, runtime_id=runtime_id)
    finally:
        clock.revoke()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Explicit native PAPER activation; no account inception')
    for name in ('root', 'record-path', 'policy-path', 'release-digest',
                 'accounts-path', 'expected-clock-source', 'runtime-id'):
        parser.add_argument('--' + name, required=True)
    args = vars(parser.parse_args(argv))
    result = commission(**{k.replace('-', '_'): v for k, v in args.items()})
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
