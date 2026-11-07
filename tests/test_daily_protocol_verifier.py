"""Frozen source/plan reconstruction must not publish or grant authority."""
import json

import pytest
from app.backtest import forecast_cli
from test_daily_afi_bridge import encode
from test_daily_probability_protocol import _content_addressed, _freeze

from scripts.observation_runtime import daily_probability_replay as replay


def verify(root, result):
    return replay.verify_daily_probability_protocol(
        bundle_root=root, companion_name=result['daily_protocol'],
        expected_companion_sha256=result['daily_protocol'][:-5])


def test_protocol_verifies_without_publisher_or_holdout(tmp_path, monkeypatch):
    _, result = _freeze(tmp_path)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}

    def forbidden(*args, **kwargs):
        raise AssertionError('Read-only protocol verification cannot publish or evaluate holdout')

    monkeypatch.setattr(replay, 'publish_research_text', forbidden)
    monkeypatch.setattr(forecast_cli, 'publish_research_text', forbidden)
    monkeypatch.setattr(replay, 'evaluate_probability_holdout', forbidden)
    checked = verify(tmp_path, result)
    assert checked['status'] == 'SYNTHETIC_DAILY_PROBABILITY_PROTOCOL_REPRODUCED'
    assert checked['protocol_sha256'] == result['protocol_sha256']
    assert checked['holdout_n'] == 2
    assert checked['independently_unseen'] is checked['startup_authorized'] is False
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize('field', ['production_approved', 'source_authenticated', 'history_completeness_verified'])
def test_rehashed_authority_refuses(tmp_path, field):
    _, result = _freeze(tmp_path)
    companion = json.loads((tmp_path/result['daily_protocol']).read_bytes())
    companion[field] = True
    name, pin = _content_addressed(tmp_path, companion)
    with pytest.raises(ValueError):
        replay.verify_daily_probability_protocol(bundle_root=tmp_path, companion_name=name,
                                                  expected_companion_sha256=pin)


@pytest.mark.parametrize('member', ['protocol', 'plan', 'request_snapshot'])
def test_missing_required_member_refuses_without_repair(tmp_path, member):
    _, result = _freeze(tmp_path)
    companion = json.loads((tmp_path/result['daily_protocol']).read_bytes())
    name = companion['protocol_result']['protocol'] if member == 'protocol' else companion[member]
    (tmp_path/name).rename(tmp_path/('retained-'+name))
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises((ValueError, OSError)):
        verify(tmp_path, result)
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


def test_mutable_entry_request_not_needed(tmp_path):
    _, result = _freeze(tmp_path)
    (tmp_path/'protocol-request.json').write_bytes(encode({'untrusted': True}))
    assert verify(tmp_path, result)['holdout_n'] == 2


def test_cli_verification_forbids_output_root(tmp_path, capsys):
    _, result = _freeze(tmp_path)
    args = ['--bundle-root', str(tmp_path), '--verify-protocol', result['daily_protocol'],
            '--expected-companion-sha256', result['daily_protocol'][:-5]]
    assert replay.main(args) == 0
    assert json.loads(capsys.readouterr().out)['holdout_n'] == 2
    with pytest.raises(SystemExit) as error:
        replay.main(args+['--output-root', str(tmp_path)])
    assert error.value.code == 2
