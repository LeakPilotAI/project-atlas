"""Static PAPER-release regression gate; no runtime import or authority grant.

Detects recognizable accidental order SDKs, order dispatch and live toggles.
Not a sandbox or proof against obfuscation/plugins; reviewed release inventory,
protected startup and actual technical/activation checks remain required. The
strict historical profile retains its original B1/C1/D1/E1 requirements;the
approved personal profile is controlled by its sole operator.
"""
import argparse
import ast
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCOPES = ('backend/app', 'scripts/observation_runtime', 'scripts/windows',
          'frontend/app', 'frontend/src', 'frontend/components', 'frontend/offline')
EXTENSIONS = {'.py', '.ps1', '.psm1', '.js', '.cjs', '.mjs', '.ts', '.tsx', '.html'}
ORDER_CALLS = {'submitorder', 'placeorder', 'createorder', 'cancelorder', 'modifyorder',
               'replaceorder', 'sendorder', 'executeorder', 'signorder', 'sendrawtransaction'}
LIVE_IDENTIFIERS = {'enablelivetrading', 'livetradingenabled', 'liveorderrouter', 'liveexecutionadapter',
                    'liveexecution', 'realcapitalaccount', 'promotepapertolive', 'livetradingtoggle'}
SDK_PREFIXES = ('ccxt', 'ib_insync', 'ibapi', 'alpaca.trading', 'alpaca_trade_api',
                'hyperliquid.exchange', 'binance.client', 'coinbase.rest')
ACCOUNT = {'strategy': 'QUALITY_DIPS', 'currency': 'USD', 'hypothetical_opening_cash': '1000',
           'max_entry_usd': '100', 'max_open_positions': 1, 'universe': 'ELIGIBLE_QD_RANKED_STOCKS_ETFS',
           'long_only': True, 'manual_entries': True, 'manual_exits': True, 'scale_in': False,
           'fractional_if_supported': True, 'overnight_allowed': True, 'legacy_adoption': False,
           'fees_bps_per_side': '2', 'slippage_bps_per_side': '2', 'cost_evidence': 'SYNTHETIC_ASSUMPTIONS_NOT_MARKET_COSTS'}
GATES = ('P1_DATA', 'P2_MANUAL_ROUTING', 'P3_RECONCILIATION', 'P4_OVERNIGHT',
         'P5_OWNED_LIFECYCLE', 'P6_RECOVERY', 'P7_SEVEN_DAY_TRIAL', 'P8_EXTENDED_TRIAL')
LOCAL_LAYOUT = {
    'schema': 'ATLAS_D_ONLY_SINGLE_ACCOUNT_V1', 'deployment_drive': 'D:',
    'windows_identity': 'EXISTING_CURRENT_ACCOUNT', 'additional_windows_accounts_allowed': False,
    'c_deployment_allowed': False, 'development_root': 'D:/Work/Project Atlas',
    'runtime_root': 'D:/AtlasRuntime/releases/<accepted-release-sha>',
    'financial_root': 'D:/AtlasPaper/QualityDips/<accepted-epoch>',
    'control_root': 'D:/AtlasPaper/QualityDips/<accepted-epoch>/control',
    'custody_root': 'D:/AtlasCustody/QualityDips/<accepted-epoch>',
    'custody_independence_established': False, 'backup_independence_established': False,
    'drive_root_acl_change_allowed': False, 'project_acl_change_allowed': False,
    'provisioning_authorized': False,
}


def check_local_paper_proposal(value):
    """Proposal lint only. Never called by startup or financial authority code."""
    fields = {'schema', 'profile_id', 'status', 'runtime_consumable', 'strict_profile_unchanged',
              'canonical_gate_changes', 'startup_authorized', 'financial_publication_authorized',
              'architecture_reference', 'account_policy_reference', 'essential_controls',
              'reduced_assurances', 'proposed_local_authority', 'refuse_on', 'acceptance_required',
              'backup_policy', 'trial_progress'}
    if (type(value) is not dict or set(value) != fields
            or value['schema'] != 'ATLAS_PAPER_SECURITY_PROFILE_PROPOSAL_V1'
            or value['profile_id'] != 'LOCAL_SUPERVISED_PAPER_V1'
            or value['status'] != 'PROPOSED_NOT_ACCEPTED'
            or value['strict_profile_unchanged'] is not True
            or type(value['canonical_gate_changes']) is not int or value['canonical_gate_changes'] != 0
            or any(value[k] is not False for k in ('runtime_consumable', 'startup_authorized', 'financial_publication_authorized'))):
        raise ValueError('LOCAL_PAPER_PROPOSAL_NOT_AUTHORITY')
    expected = {
        'essential_controls': {'NATIVE_IDENTITY_EXACT_ACL', 'APPEND_ONLY_DURABLE_EVIDENCE', 'SINGLE_INCEPTION_NO_REPLAY',
            'UNKNOWN_BLOCKS_EFFECTS', 'MANUAL_ENTRY_EXIT', 'EXACT_ACCOUNTING', 'STARTUP_RECOVERY_INTEGRITY',
            'OWNED_SHUTDOWN_RESTART', 'FRESH_DATA_OR_REFUSAL', 'NO_REAL_ORDER_EXECUTION'},
        'reduced_assurances': {'EXISTING_ACCOUNT_TRUSTED_NOT_ADVERSARIAL_ISOLATION', 'LOCAL_KEY_NOT_INDEPENDENT_ISSUER',
            'LOCAL_HIGH_WATER_NOT_INDEPENDENT_ROLLBACK_PROOF', 'OS_UTC_NOT_CRYPTOGRAPHIC_TIME_AUTHORITY',
            'D_BACKUP_NOT_DEVICE_LOSS_PROTECTION'},
        'refuse_on': {'MISSING_OR_CONFLICTING_RECORD', 'CORRUPTION_OR_INVALID_SIGNATURE', 'WRONG_RESOURCE_IDENTITY_OR_ACL',
            'OBSERVED_REVISION_ROLLBACK', 'UNKNOWN_FINANCIAL_EFFECT', 'STALE_OR_UNVERIFIED_MARKET_DATA',
            'CLOCK_UNCERTAINTY', 'UNKNOWN_OR_UNDRAINED_WRITER', 'UNAPPROVED_PROFILE_OR_PROCESS'},
        'acceptance_required': {'FORMAL_PROFILE_SCOPED_GOVERNANCE_DISPOSITION', 'EXPLICIT_OPERATOR_RISK_ACKNOWLEDGEMENT',
            'REVIEWED_LOCAL_ADAPTERS_AND_NATIVE_ACCEPTANCE', 'SEPARATE_REAL_PUBLICATION_AND_STARTUP_PERMISSION'},
    }
    for field, entries in expected.items():
        items = value[field]
        if type(items) is not list or any(type(item) is not str for item in items) or len(items) != len(entries) or set(items) != entries:
            raise ValueError('LOCAL_PAPER_PROPOSED_CONTROL_OR_LIMITATION_MISSING')
    if (value['architecture_reference'] != 'ATLAS_DEPLOYMENT_POLICY.json#local_layout'
            or value['account_policy_reference'] != 'ATLAS_PAPER_RELEASE_POLICY.json#account'
            or value['backup_policy'] != 'D_ONLY_VERSIONED_BACKUPS_LIMITED_TO_LOGICAL_RECOVERY_NO_INDEPENDENT_OFFLINE_GUARANTEE'
            or type(value['trial_progress']) is not dict
            or json.dumps(value['trial_progress'], sort_keys=True) != json.dumps(
                {'authorized_days': 0, 'seven_day_target': 7, 'extended_sessions': 0,
                 'extended_target_min': 30, 'extended_target_max': 60}, sort_keys=True)
            or type(value['proposed_local_authority']) is not dict
            or set(value['proposed_local_authority']) != {'authorization', 'signing', 'coordination', 'clock', 'ownership', 'recovery'}
            or any(type(s) is not str or not 1 <= len(s) <= 256 for s in value['proposed_local_authority'].values())):
        raise ValueError('LOCAL_PAPER_PROPOSAL_SCOPE_MISMATCH')


def check_autonomous_paper_proposal(value):
    """Design-proposal checks only; not an execution policy or authority issuer."""
    fields = {'schema', 'profile_id', 'status', 'supersedes', 'target_authority', 'runtime_consumable',
              'startup_authorized', 'financial_publication_authorized', 'provider_connection_authorized',
              'canonical_gate_changes', 'strict_profile_unchanged', 'architecture_reference',
              'security_reduction_reference', 'account', 'automation', 'essential_controls', 'l1_contract',
              'simulation', 'pipeline', 'acceptance_required', 'trial_progress'}
    if (type(value) is not dict or set(value) != fields
            or value['schema'] != 'ATLAS_AUTONOMOUS_PAPER_PROPOSAL_V1'
            or value['profile_id'] != 'AUTONOMOUS_PAPER_ONLY_V1'
            or value['status'] != 'PROPOSED_NOT_ACCEPTED' or value['supersedes'] != 'LOCAL_SUPERVISED_PAPER_V1'
            or value['target_authority'] != 'EXPLICIT_OPERATOR_DESIGN_REQUIREMENT_NOT_OPERATIONAL_ACCEPTANCE'
            or value['strict_profile_unchanged'] is not True
            or type(value['canonical_gate_changes']) is not int or value['canonical_gate_changes'] != 0
            or any(value[k] is not False for k in ('runtime_consumable', 'startup_authorized',
                                                  'financial_publication_authorized', 'provider_connection_authorized'))):
        raise ValueError('AUTONOMOUS_PROPOSAL_NOT_RUNTIME_AUTHORITY')
    account = {k: ACCOUNT[k] for k in ('strategy', 'currency', 'hypothetical_opening_cash', 'max_open_positions',
               'universe', 'long_only', 'scale_in', 'fractional_if_supported', 'overnight_allowed',
               'legacy_adoption', 'fees_bps_per_side', 'slippage_bps_per_side')}
    account.update(max_entry_notional_usd='100', force_end_of_day_liquidation=False, borrowing=False, leverage=False)
    automation = {'session_authorization': 'EXPLICIT_OPERATOR_SCOPED_BOUNDED_SESSION', 'per_trade_confirmation': False,
        **dict.fromkeys(('automatic_discovery', 'automatic_ranking', 'automatic_entries', 'automatic_position_management',
                        'automatic_partial_full_exits', 'automatic_risk_enforcement', 'automatic_financial_recording',
                        'automatic_reconciliation'), True),
        'global_pause': 'CLOSE_NEW_ENTRY_ADMISSION_KEEP_VALID_RISK_MANAGEMENT',
        'global_stop': 'CLOSE_ENTRY_ADMISSION_HALT_NEW_DISPATCH_DRAIN_RECONCILE_PRESERVE_POSITIONS',
        'resume': 'NEW_EXPLICIT_SESSION_AUTHORIZATION', 'end_of_day': 'PRESERVE_OPEN_POSITIONS_NO_FORCED_LIQUIDATION'}
    for field, expected in (('account', account), ('automation', automation)):
        if json.dumps(value[field], sort_keys=True) != json.dumps(expected, sort_keys=True):
            raise ValueError('AUTONOMOUS_TARGET_OR_RISK_LIMIT_CHANGED')
    lists = {
        'essential_controls': {'NATIVE_IDENTITY_EXACT_ACL', 'APPEND_ONLY_DURABLE_EVIDENCE', 'SINGLE_INCEPTION_NO_REPLAY',
            'UNKNOWN_BLOCKS_EFFECTS', 'EXACT_ACCOUNTING', 'STARTUP_RECOVERY_INTEGRITY', 'OWNED_SHUTDOWN_RESTART',
            'FRESH_DATA_OR_REFUSAL', 'NO_REAL_ORDER_EXECUTION', 'SESSION_AUTHORITY_NO_PER_TRADE_PROMPTS',
            'ENTITLEMENT_BOUND_L1', 'GLOBAL_STOP_PAUSE'},
        'acceptance_required': {'FORMAL_AUTONOMOUS_PROFILE_SCOPED_GOVERNANCE_DISPOSITION',
            'OPERATOR_SESSION_AND_LOCAL_SECURITY_RISK_ACKNOWLEDGEMENT', 'REVIEWED_AUTONOMOUS_ROUTING_AND_RISK_ACCEPTANCE',
            'EXPLICIT_FINANCIAL_PUBLICATION_PERMISSION', 'PROVIDER_RIGHTS_AND_CONNECTION_PERMISSION',
            'EXPLICIT_SUPERVISED_AUTONOMOUS_PAPER_START_PERMISSION'},
    }
    for field, entries in lists.items():
        items = value[field]
        if type(items) is not list or any(type(v) is not str for v in items) or len(items) != len(entries) or set(items) != entries:
            raise ValueError('AUTONOMOUS_CONTROL_OR_ACCEPTANCE_MISSING')
    l1 = value['l1_contract']; simulation = value['simulation']
    if (type(l1) is not dict or l1.get('proposal_schema') != 'QD_L1_EVIDENCE_PROPOSAL_V1'
            or set(l1) != {'proposal_schema', 'required_fields', 'missing_optional_source_fields', 'no_size_evidence',
                           'freshness_spread_and_size_limits', 'display'}
            or l1.get('required_fields') != ['provider_id', 'feed_id', 'entitlement_id', 'feed_scope', 'delay_status', 'instrument_id', 'asset_class',
                'currency', 'bid', 'ask', 'source_timestamp', 'received_timestamp', 'sequence_or_dedup_identity',
                'session', 'exchange_calendar_identity', 'market_status', 'connection_status', 'size_units', 'bid_size', 'ask_size']
            or l1.get('missing_optional_source_fields') != 'UNAVAILABLE_NOT_FABRICATED'
            or l1.get('no_size_evidence') != 'DISPLAY_IF_AUTHORIZED_NO_SIMULATED_FILL'
            or l1.get('freshness_spread_and_size_limits') != 'ACCEPTED_PARAMETERS_REQUIRED_NO_SILENT_DEFAULT'
            or l1.get('display') != 'OBSERVED_L1_SEPARATE_FROM_HYPOTHETICAL_FILLS'
            or type(simulation) is not dict or simulation.get('entry_reference') != 'ASK' or simulation.get('exit_reference') != 'BID'
            or set(simulation) != {'model', 'entry_reference', 'exit_reference', 'fees', 'slippage', 'double_count_costs',
                                  'liquidity', 'initial_execution_session', 'no_fill_on', 'unknown_effect'}
            or simulation.get('model') != 'PROPOSED_VERSIONED_TOP_OF_BOOK_NO_REAL_EXECUTION'
            or simulation.get('double_count_costs') is not False
            or simulation.get('fees') != '2_BPS_EACH_SIDE_REFERENCE_NOTIONAL'
            or simulation.get('slippage') != '2_BPS_EACH_SIDE_REFERENCE_NOTIONAL_SEPARATE_COST'
            or simulation.get('liquidity') != 'VERIFIED_SIZE_UNITS_AND_ACCEPTED_PARTICIPATION_CAP_REQUIRED'
            or simulation.get('unknown_effect') != 'BLOCK_REPLAY_AND_NEW_EFFECTS_RECONCILE_ONLY'
            or simulation.get('initial_execution_session') != 'REGULAR_ONLY_EXTENDED_DISPLAY_IF_LICENSED'
            or simulation.get('no_fill_on') != ['STALE_OR_MISSING_QUOTE', 'MISSING_OR_AMBIGUOUS_SIZE', 'DISCONNECTED_FEED',
                'CROSSED_OR_INVALID_QUOTE', 'MARKET_CLOSED', 'HALTED_OR_UNKNOWN_STATUS', 'CLOCK_UNCERTAINTY',
                'UNACCEPTED_INSTRUMENT', 'RISK_OR_CASH_REFUSAL', 'UNKNOWN_PRIOR_EFFECT']):
        raise ValueError('L1_SIMULATION_EVIDENCE_OR_REFUSAL_REQUIRED')
    if (value['architecture_reference'] != 'ATLAS_DEPLOYMENT_POLICY.json#local_layout'
            or value['security_reduction_reference'] != 'LOCAL_SUPERVISED_PAPER_PROFILE_PROPOSAL_V1.json#reduced_assurances'
            or value['pipeline'] != ['MARKET_DATA', 'CANDIDATE_RANKING', 'SIGNAL_VALIDATION', 'RISK_ADMISSION',
                'SIMULATED_EXECUTION', 'IMMUTABLE_LEDGER', 'POSITION_MANAGEMENT', 'AUTOMATED_EXITS',
                'RECONCILIATION', 'ORIGINAL_DASHBOARD']
            or json.dumps(value['trial_progress'], sort_keys=True) != json.dumps(
                {'authorized_days': 0, 'seven_day_target': 7, 'extended_sessions': 0,
                 'extended_target_min': 30, 'extended_target_max': 60}, sort_keys=True)):
        raise ValueError('AUTONOMOUS_PROPOSAL_SCOPE_OR_TRIAL_CHANGED')


def normalized(value):
    return re.sub('[^a-z0-9]', '', value.lower())


def check_policy(policy, deployment):
    forbidden = ('live_money_implementation_allowed', 'real_order_routing_allowed',
                 'real_capital_enrollment_allowed', 'paper_to_live_promotion_allowed',
                 'live_toggle_or_dormant_path_allowed', 'operational_startup_authorized',
                 'financial_provisioning_authorized')
    fields = {'schema', 'decision_date', 'release_program', 'authority', 'deployment', 'account', 'account_acceptance',
              'required_blocked_gates', 'canonical_governance_decisions_changed', 'paper_release_gates',
              'retained_legacy_safety_guards', 'deployment_policy_reference', *forbidden}
    if (type(policy) is not dict or set(policy) != fields or policy.get('schema') != 'ATLAS_PAPER_RELEASE_POLICY_V1'
            or policy['release_program'] != 'PAPER_FIRST_NO_LIVE_MONEY_IMPLEMENTATION'
            or policy['authority'] != 'EXPLICIT_OPERATOR_SCOPE_NOT_ACCEPTANCE'
            or policy['deployment'] != 'SINGLE_USER_WINDOWS_LOCAL'
            or type(policy['canonical_governance_decisions_changed']) is not int or policy['canonical_governance_decisions_changed'] != 0):
        raise ValueError('PAPER_POLICY_VERSION_OR_SCOPE_REQUIRED')
    if any(policy.get(k) is not False for k in forbidden):
        raise ValueError('PAPER_SCOPE_MUST_NOT_GRANT_LIVE_OR_STARTUP_AUTHORITY')
    if (type(policy.get('account')) is not dict or json.dumps(policy['account'], sort_keys=True) != json.dumps(ACCOUNT, sort_keys=True)
            or policy.get('account_acceptance') != 'OPERATOR_INTENT_NOT_INDEPENDENT_ACCEPTANCE'
            or policy.get('required_blocked_gates') != ['B1', 'C1', 'D1', 'E1']):
        raise ValueError('PAPER_ACCOUNT_OR_ACCEPTANCE_SCOPE_MISMATCH')
    gates = policy.get('paper_release_gates')
    if type(gates) is not dict or set(gates) != set(GATES):
        raise ValueError('PAPER_GATE_INVENTORY_MISMATCH')
    for gate in gates.values():
        if (type(gate) is not dict or set(gate) != {'status', 'required_evidence', 'acceptance'}
                or gate['status'] not in ('BLOCKED', 'NOT_STARTED') or type(gate['required_evidence']) is not list
                or not 1 <= len(gate['required_evidence']) <= 16
                or any(type(item) is not str or not 1 <= len(item) <= 512 for item in gate['required_evidence'])
                or gate['acceptance'] != 'INDEPENDENT_REVIEW_AND_EXPLICIT_OPERATOR_PERMISSION_REQUIRED'):
            raise ValueError('PAPER_GATE_NOT_INDEPENDENTLY_ACCEPTED')
    if (deployment.get('deployment') != 'SINGLE_USER_WINDOWS_LOCAL'
            or any(deployment.get(k) is not False for k in ('vps_allowed','cloud_hosting_allowed','live_money_authorized',
                                                         'live_money_implementation_allowed','paper_startup_authorized'))
            or deployment.get('release_program') != 'PAPER_FIRST_NO_LIVE_MONEY_IMPLEMENTATION'
            or deployment.get('production') != 'NO_GO'):
        raise ValueError('LOCAL_PAPER_DEPLOYMENT_MISMATCH')
    if (policy.get('deployment_policy_reference') != 'ATLAS_DEPLOYMENT_POLICY.json#local_layout'
            or type(deployment.get('local_layout')) is not dict
            or json.dumps(deployment['local_layout'], sort_keys=True) != json.dumps(LOCAL_LAYOUT, sort_keys=True)
            or deployment.get('financial_storage') != 'D_ONLY_ACCEPTED_CHILD_RESOURCES_CURRENT_WINDOWS_ACCOUNT'):
        raise ValueError('D_ONLY_SINGLE_ACCOUNT_LAYOUT_REQUIRED')


def source_findings(name, source, *, retained_false=False):
    """No execution/import of inspected application code or financial records."""
    found = set()
    if name.endswith('.py'):
        tree = ast.parse(source, filename=name)
        retained_targets = {id(target) for node in ast.walk(tree) if isinstance(node, ast.Assign)
                            and isinstance(node.value, ast.Constant) and node.value.value is False
                            for target in node.targets if isinstance(target, ast.Name) and target.id == 'LIVE_EXECUTION'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                call = fn.attr if isinstance(fn, ast.Attribute) else fn.id if isinstance(fn, ast.Name) else ''
                if normalized(call) in ORDER_CALLS:
                    found.add('ORDER_ROUTING_CALL')
                if (isinstance(fn, ast.Name) and fn.id == 'getattr' and len(node.args) > 1
                        and isinstance(node.args[1], ast.Constant)
                        and normalized(str(node.args[1].value)) in ORDER_CALLS):
                    found.add('ORDER_ROUTING_CALL')
                if (isinstance(fn, ast.Name) and fn.id == '__import__' and node.args and isinstance(node.args[0], ast.Constant)
                        and str(node.args[0].value).startswith(SDK_PREFIXES)):
                    found.add('ORDER_SDK_IMPORT')
                if (isinstance(fn, ast.Attribute) and fn.attr == 'import_module' and node.args and isinstance(node.args[0], ast.Constant)
                        and str(node.args[0].value).startswith(SDK_PREFIXES)):
                    found.add('ORDER_SDK_IMPORT')
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imports = [a.name for a in node.names] if isinstance(node, ast.Import) else [
                    node.module or '', *((node.module or '') + '.' + alias.name for alias in node.names)]
                if any(value == p or value.startswith(p + '.') for value in imports for p in SDK_PREFIXES):
                    found.add('ORDER_SDK_IMPORT')
            identifier = node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else node.name if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) else ''
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and normalized(identifier) in ORDER_CALLS:
                found.add('DORMANT_ORDER_ROUTING_FUNCTION')
            status_read = normalized(identifier) == 'liveexecution' and isinstance(node, (ast.Name, ast.Attribute)) and isinstance(node.ctx, ast.Load)
            if (normalized(identifier) in LIVE_IDENTIFIERS and not status_read
                    and not (retained_false and id(node) in retained_targets)):
                found.add('LIVE_PATH_OR_TOGGLE')
            if isinstance(node, ast.Constant) and type(node.value) is str:
                value = node.value
                if (re.fullmatch(r'[A-Za-z_]+', value)
                        and normalized(value.removeprefix('ATLAS_')) in LIVE_IDENTIFIERS - {'liveexecution'}):
                    found.add('LIVE_PATH_OR_TOGGLE')
                if re.fullmatch(r'/(?:api/)?(?:live|broker|real-money)/(?:orders?|accounts?)(?:/.*)?', value):
                    found.add('LIVE_ORDER_OR_ACCOUNT_ROUTE')
                if re.search(r'https?://[^ ]+(?:/v\d+/orders?|/api/v\d+/order|/exchange)(?:\?|$)', value):
                    found.add('REMOTE_ORDER_ENDPOINT')
    else:
        # Recognizable dispatch/toggles across PowerShell/JS/HTML. Static text
        # saying "no real orders" is not an executable order call.
        identifiers = re.findall(r'[A-Za-z_][A-Za-z0-9_]*\s*(?=\()', source)
        if any(normalized(value.strip()) in ORDER_CALLS for value in identifiers): found.add('ORDER_ROUTING_CALL')
        if any(normalized(value.strip()) in LIVE_IDENTIFIERS for value in identifiers): found.add('LIVE_PATH_OR_TOGGLE')
        assignments = re.findall(r'\b([A-Za-z_][A-Za-z0-9_]*)\s*(?=[:=](?!=))', source)
        if any(normalized(value) in LIVE_IDENTIFIERS for value in assignments):
            found.add('LIVE_PATH_OR_TOGGLE')
        if re.search(r'(?:/api)?/live/orders?\b', source): found.add('LIVE_ORDER_OR_ACCOUNT_ROUTE')
    return sorted(found)


def audit(root=ROOT):
    policy = json.loads((root/'docs/ATLAS_PAPER_RELEASE_POLICY.json').read_text(encoding='utf-8'))
    deployment = json.loads((root/'docs/ATLAS_DEPLOYMENT_POLICY.json').read_text(encoding='utf-8'))
    check_policy(policy, deployment)
    issues, count = [], 0
    retained = policy.get('retained_legacy_safety_guards', {})
    if set(retained) != {'backend/app/prediction/policy.py'}:
        raise ValueError('RETAINED_SAFETY_GUARD_INVENTORY_MISMATCH')
    if any(not (root / name).is_file() for name in retained):
        raise ValueError('RETAINED_SAFETY_GUARD_MISSING')
    for scope in SCOPES:
        folder = root/scope
        if not folder.exists(): continue
        for path in sorted(folder.rglob('*')):
            if (not path.is_file() or path.suffix not in EXTENSIONS
                    or '.test.' in path.name
                    or any(part in ('node_modules', '__pycache__', '.next', 'vendor') for part in path.relative_to(folder).parts)):
                continue
            if path.is_symlink() or path.is_junction(): raise ValueError('SOURCE_ALIAS_REQUIRES_REVIEW')
            name = path.relative_to(root).as_posix()
            raw = path.read_bytes()
            # Source-only baseline survives Git's Windows CRLF/Linux LF checkout.
            # This is never used for financial bytes, native identity or custody.
            unchanged = name in retained and hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest() == retained[name]
            findings = source_findings(name, raw.decode('utf-8-sig'), retained_false=unchanged)
            if name in retained and not unchanged:
                findings.append('LEGACY_SAFETY_GUARD_CHANGED')
            count += 1
            if findings: issues.append({'path': name, 'findings': findings})
    personal_path=root/'docs/ATLAS_PERSONAL_PAPER_RELEASE_POLICY.json'
    if personal_path.exists():
        personal=json.loads(personal_path.read_text(encoding='utf8'))
        if (personal.get('schema')!='ATLAS_PERSONAL_PAPER_RELEASE_POLICY_V1' or personal.get('policy_approved') is not True
                or personal.get('profile_id')!='PERSONAL_PAPER_ONLY_V1'
                or personal.get('startup_authorized') is not False or personal.get('activation_authorized') is not False
                or any(personal['authority'][k] is not False for k in ('external_reviewer_required','external_issuer_required','independent_custodian_required','per_trade_confirmation'))):
            raise ValueError('PERSONAL_POLICY_OR_ACTIVATION_BOUNDARY_INVALID')
    return {'schema':'ATLAS_PAPER_STATIC_AUDIT_V1','source_files':count,'issues':issues,
            'operational_acceptance':False,'startup_authorized':False}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    check_local_paper_proposal(json.loads((ROOT/'docs/LOCAL_SUPERVISED_PAPER_PROFILE_PROPOSAL_V1.json').read_text()))
    check_autonomous_paper_proposal(json.loads((ROOT/'docs/AUTONOMOUS_PAPER_ONLY_PROFILE_PROPOSAL_V1.json').read_text()))
    result=audit()
    print(json.dumps(result,indent=2))
    raise SystemExit(bool(result['issues']))
