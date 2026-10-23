"""Coverage presentation explains missing evidence without inventing outcomes."""
import hashlib
import json

import pytest
from test_daily_holdout_diagnostics import evaluate
from test_daily_probability_protocol import _freeze

from scripts.observation_runtime import daily_holdout_visual as visual


def arguments(root):
    source, frozen = _freeze(root)
    result = evaluate(root, source, frozen)
    return {'bundle_root': root, 'companion_name': result['daily_holdout'],
            'expected_companion_sha256': result['daily_holdout'][:-5]}


def test_render_is_readonly_inert_and_has_accessible_denominators(tmp_path):
    args = arguments(tmp_path)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    text = visual.render_daily_holdout_coverage(**args)
    assert 'Requested 2 = refused 0 + issued 2' in text
    assert 'Issued 2 = resolved 2 + unscored 0' in text
    assert text.count('<table>') == 2 and '<caption>' in text
    assert "connect-src 'none'" in text and "default-src 'none'" in text
    assert '<script' not in text and '<form' not in text and 'http://' not in text
    assert 'does not prove a missed market event' in text
    assert 'INSUFFICIENT_EVIDENCE' in text and 'production NO-GO' in text
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


def test_publication_is_content_addressed_idempotent_and_denied(tmp_path):
    args = arguments(tmp_path)
    first = visual.publish_daily_holdout_coverage(**args, output_root=tmp_path)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert visual.publish_daily_holdout_coverage(**args, output_root=tmp_path) == first
    assert hashlib.sha256((tmp_path/first['html']).read_bytes()).hexdigest() == first['html_sha256']
    assert first['startup_authorized'] is first['trading_authorized'] is False
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


def test_foreign_output_and_publication_failure_are_not_success(tmp_path, monkeypatch):
    args = arguments(tmp_path)
    other = tmp_path/'other'
    other.mkdir()
    with pytest.raises(ValueError):
        visual.publish_daily_holdout_coverage(**args, output_root=other)
    assert list(other.iterdir()) == []

    def failed(*a, **k):
        raise OSError('synthetic full disk')

    monkeypatch.setattr(visual, 'publish_research_text', failed)
    with pytest.raises(OSError, match='full disk'):
        visual.publish_daily_holdout_coverage(**args, output_root=tmp_path)


def test_coverage_cli_and_missing_source_refusal(tmp_path, capsys):
    args = arguments(tmp_path)
    cli = ['--bundle-root', str(tmp_path), '--companion', args['companion_name'],
           '--expected-companion-sha256', args['expected_companion_sha256'], '--output-root', str(tmp_path)]
    assert visual.main(cli) == 0
    assert json.loads(capsys.readouterr().out)['native_browser_acceptance'] == 'NOT_ESTABLISHED'
    companion = json.loads((tmp_path/args['companion_name']).read_bytes())
    path = tmp_path/companion['holdout_result']['report']
    path.rename(tmp_path/'retained-report')
    with pytest.raises(SystemExit) as error:
        visual.main(cli)
    assert error.value.code == 2
