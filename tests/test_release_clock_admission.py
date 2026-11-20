"""Offline immutable candidate clock identity refusal tests."""
from pathlib import Path
import pytest
from scripts.release_clock_admission import (
    clock_constants, require_candidate_clock_identity, verify_source_file,
)

ROOT = Path(__file__).resolve().parents[1]
CLOCK = ROOT / 'scripts/observation_runtime/personal_v8_operator_clock.py'


def test_actual_v8_contract_refuses_new_release_identity():
    source = CLOCK.read_text(encoding='utf-8')
    values = clock_constants(source)
    assert values['PROFILE'] == 'V8_INDEPENDENT_NTP_OPERATOR_CLOCK_V1'
    with pytest.raises(ValueError, match='CLOCK_ADMISSION_RELEASE_IDENTITY_MISMATCH'):
        require_candidate_clock_identity(source=source, candidate_commit='a'*40,
            artifact_digest=values['ARTIFACT'], receipt_sha256=values['APP_RECEIPT'])


def test_matching_exact_clock_contract_is_admitted_as_source_only():
    values = clock_constants(CLOCK.read_text(encoding='utf-8'))
    assert verify_source_file(path=CLOCK, candidate_commit=values['APP'],
        artifact_digest=values['ARTIFACT'], receipt_sha256=values['APP_RECEIPT']) == values


@pytest.mark.parametrize('field', ['APP', 'ARTIFACT', 'APP_RECEIPT'])
def test_each_bound_identity_must_match(field):
    source = CLOCK.read_text(encoding='utf-8')
    values = clock_constants(source)
    arguments = dict(candidate_commit=values['APP'], artifact_digest=values['ARTIFACT'],
                     receipt_sha256=values['APP_RECEIPT'])
    arguments[{'APP':'candidate_commit', 'ARTIFACT':'artifact_digest',
               'APP_RECEIPT':'receipt_sha256'}[field]] = ('0' * (40 if field == 'APP' else 64))
    with pytest.raises(ValueError, match='CLOCK_ADMISSION_RELEASE_IDENTITY_MISMATCH'):
        require_candidate_clock_identity(source=source, **arguments)


def test_missing_or_dynamic_identity_refused():
    source = CLOCK.read_text(encoding='utf-8')
    with pytest.raises(ValueError, match='CLOCK_ADMISSION_MISSING_IDENTITY'):
        clock_constants(source.replace('APP = ', 'RELEASE = ', 1))
    with pytest.raises(ValueError, match='CLOCK_ADMISSION_DYNAMIC_IDENTITY_REFUSED'):
        clock_constants(source.replace('APP = "', 'APP = str("', 1).replace(
            'c8cc4846508b29483d10a0b4c4353f8a26f1fc9c"',
            'c8cc4846508b29483d10a0b4c4353f8a26f1fc9c")', 1))


def test_invalid_candidate_refused_before_source_check():
    with pytest.raises(ValueError, match='CLOCK_ADMISSION_INVALID_CANDIDATE'):
        require_candidate_clock_identity(source='not python', candidate_commit='v8',
                                         artifact_digest='0'*64, receipt_sha256='0'*64)
