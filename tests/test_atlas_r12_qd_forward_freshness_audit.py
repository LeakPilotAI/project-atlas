"""Read-only historical shadow vs operational QD forward-source admission."""
import json
import subprocess
from datetime import datetime,timedelta,timezone
from pathlib import Path

import pytest

from scripts.observation_runtime import atlas_r12_qd_forward_freshness_audit as audit
from app.investment.quality_dips_v3_forward_readiness import forward_readiness

REFERENCE='2026-11-09T10:42:00+00:00'


def sample(tmp_path,*,days=20,first_day='2026-10-20T15:00:00+00:00',complete=True):
    path=tmp_path/'synthetic_shadow.jsonl'
    stamp=datetime.fromisoformat(first_day)
    rows=[]
    for d in range(days):
        for i in range(10):
            rows.append(json.dumps({'timestamp':(stamp+timedelta(days=d,seconds=i)).isoformat(),
                                    'symbol':f'S{i}','patient_state':'WATCH'}))
    raw='\n'.join(rows)+('\n' if complete else '')
    path.write_text(raw,encoding='utf-8')
    return path


def native():
    return {'schema':'ATLAS_QD_NATIVE_SOURCE_INVENTORY_V1',
      'source_parent_present':True,'ordinary_child_count':2,
      'operational_publication_verified':False}


def test_actual_shadow_coverage_ready_but_stale_and_never_operational():
    out=audit.inspect(reference_utc=REFERENCE)
    assert out['historical_shadow_thresholds_met'] is True
    assert out['historical_evaluations']==224817
    assert out['historical_symbols']==36
    assert out['historical_unique_days']==24
    assert out['shadow_journal_bytes']==223956704
    assert out['shadow_last_event_utc']=='2026-10-16T12:57:22.239261+00:00'
    assert out['shadow_last_event_age_days']>=23.9
    assert out['shadow_last_event_recent_by_diagnostic_3_day_limit'] is False
    assert out['qd_native_custody_children']==2
    assert out['qd_native_forward_publication_verified'] is False
    assert out['operational_qd_source_accepted'] is False
    assert out['startup_authorized'] is False
    assert out['financial_paper_gates_accepted']==0
    assert out['provider_connections_opened'] is False
    assert out['orders_submitted'] is False


def test_old_shadow_threshold_pass_is_not_new_native_source_permission(tmp_path):
    path=sample(tmp_path)
    assert forward_readiness(path)['ready'] is True
    tail=audit.tail_evidence(path)
    result=audit.evaluate(historical=forward_readiness(path),tail=tail,
                          native=native(),reference_utc=REFERENCE)
    assert result['shadow_last_event_recent_by_diagnostic_3_day_limit'] is True
    assert result['historical_shadow_thresholds_met'] is True
    assert result['operational_qd_source_accepted'] is False
    assert result['native_publication_acknowledged'] is False
    assert result['independent_provider_iex_rights_verified'] is False
    assert result['financial_clock_verified'] is False
    assert result['financial_paper_gates_accepted']==0


def test_stale_journal_refuses_currentness_even_with_high_historical_coverage(tmp_path):
    path=sample(tmp_path,first_day='2026-09-01T15:00:00+00:00')
    result=audit.evaluate(historical=forward_readiness(path),
       tail=audit.tail_evidence(path),native=native(),reference_utc=REFERENCE)
    assert result['historical_shadow_thresholds_met'] is True
    assert result['shadow_last_event_recent_by_diagnostic_3_day_limit'] is False
    assert result['operational_qd_source_accepted'] is False


def test_incomplete_trailing_json_never_skipped_silently(tmp_path):
    path=sample(tmp_path,complete=False)
    with pytest.raises(ValueError,match='R12_QD_FORWARD_JOURNAL_PARTIAL_LAST_RECORD'):
        audit.tail_evidence(path)
    path=sample(tmp_path)
    with path.open('ab') as f:f.write(b'{"timestamp":NOT_JSON}\n')
    with pytest.raises(ValueError,match='R12_QD_FORWARD_LAST_RECORD_MALFORMED'):
        audit.tail_evidence(path)


def test_missing_or_symlinked_shadow_source_refused(tmp_path):
    with pytest.raises(ValueError,match='R12_QD_FORWARD_JOURNAL_ABSENT_OR_UNSAFE'):
        audit.tail_evidence(tmp_path/'missing.jsonl')
    raw=sample(tmp_path)
    link=tmp_path/'link.jsonl'
    try:link.symlink_to(raw)
    except (OSError,NotImplementedError):pytest.skip('No symlink privilege in test environment')
    with pytest.raises(ValueError,match='R12_QD_FORWARD_JOURNAL_ABSENT_OR_UNSAFE'):
        audit.tail_evidence(link)


def test_untrusted_naive_or_future_time_refused(tmp_path):
    tail=audit.tail_evidence(sample(tmp_path))
    historical=forward_readiness(sample(tmp_path))
    with pytest.raises(ValueError,match='R12_QD_FORWARD_AWARE_UTC_REQUIRED'):
        audit.evaluate(historical=historical,tail=tail,native=native(),
                       reference_utc='2026-11-09T10:42:00')
    with pytest.raises(ValueError,match='R12_QD_FORWARD_EVENT_FROM_UNTRUSTED_FUTURE'):
        audit.evaluate(historical=historical,tail=tail,native=native(),
                       reference_utc='2026-10-01T10:42:00Z')


def test_broadened_historical_authority_and_native_missing_refuse(tmp_path):
    path=sample(tmp_path)
    h=forward_readiness(path);h['live_capital_allowed']=True
    with pytest.raises(ValueError,match='R12_QD_FORWARD_HISTORICAL_SCOPE_REFUSED'):
        audit.evaluate(historical=h,tail=audit.tail_evidence(path),native=native(),
                       reference_utc=REFERENCE)
    h['live_capital_allowed']=False
    n=native();n['operational_publication_verified']='YES'
    with pytest.raises(ValueError,match='R12_QD_FORWARD_NATIVE_CUSTODY_INVALID'):
        audit.evaluate(historical=h,tail=audit.tail_evidence(path),native=n,
                       reference_utc=REFERENCE)


def test_no_current_operational_authority_even_if_native_inventory_claims_true(tmp_path):
    path=sample(tmp_path)
    n=native();n['operational_publication_verified']=True
    out=audit.evaluate(historical=forward_readiness(path),
       tail=audit.tail_evidence(path),native=n,reference_utc=REFERENCE)
    assert out['qd_native_forward_publication_verified'] is True
    assert out['operational_qd_source_accepted'] is False
    assert out['financial_paper_gates_accepted']==0
    assert out['startup_authorized'] is False


def test_live_readonly_audit_cli_exits_no_go_and_has_no_credentials():
    root=Path(__file__).resolve().parents[1]
    p=subprocess.run([str(root/'backend/.venv/Scripts/python.exe'),'-B',
       '-m','scripts.observation_runtime.atlas_r12_qd_forward_freshness_audit',
       '--as-of-utc',REFERENCE],cwd=root,capture_output=True,text=True,timeout=60)
    assert p.returncode==2,p.stderr
    x=json.loads(p.stdout)
    assert x['historical_evaluations']==224817
    assert x['operational_qd_source_accepted'] is False
    assert x['provider_connections_opened'] is False
    assert x['paper_accounts_created'] is False
    assert x['orders_submitted'] is False
    assert x['financial_paper_gates_accepted']==0
