"""Explicit CLI retry preserves partial synthetic evidence without granting authority."""
import hashlib
import json

import pytest
from test_daily_holdout_continuation import setup
from test_daily_holdout_preview import snapshot
from test_daily_holdout_update import fixture, write

from scripts.observation_runtime import daily_holdout_update as update


@pytest.fixture(scope='module')
def seed(tmp_path_factory):
    root = tmp_path_factory.mktemp('cli-source')
    exported, companion = setup(root)
    return root, exported, companion


def test_final_companion_failure_is_not_success_and_explicit_retry_is_idempotent(
    tmp_path, seed, monkeypatch, capsys,
):
    root, request = fixture(tmp_path, seed)
    name = write(root, request)
    before = snapshot(root)
    publisher = update.publish_research_text

    def interrupt(destination, text, **kwargs):
        if json.loads(text).get('schema') == 'ATLAS_SYNTHETIC_HOLDOUT_UPDATE_RESULT_V1':
            raise OSError('synthetic private path must not appear in CLI output')
        return publisher(destination, text, **kwargs)

    monkeypatch.setattr(update, 'publish_research_text', interrupt)
    with pytest.raises(SystemExit) as failure:
        update.main(['--bundle-root', str(root), '--request', name])
    assert failure.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ''
    assert captured.err == 'Holdout update refused or incomplete; preserve all source/partial evidence.\n'
    partial = snapshot(root)
    assert len(partial) > len(before)
    assert all(partial[key] == raw for key, raw in before.items())

    monkeypatch.setattr(update, 'publish_research_text', publisher)
    assert update.main(['--bundle-root', str(root), '--request', name]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['startup_authorized'] is False
    after = snapshot(root)
    assert all(after[key] == raw for key, raw in partial.items())
    assert len(after) == len(partial) + 1  # Only the missing final companion.
    assert update.main(['--bundle-root', str(root), '--request', name]) == 0
    assert json.loads(capsys.readouterr().out) == result
    assert snapshot(root) == after
    assert update.main(['--bundle-root', str(root), '--verify', result['companion'],
                        '--expected-companion-sha256', result['companion'].split('/')[-1][:-5]]) == 0
    verified = json.loads(capsys.readouterr().out)
    assert verified['status'] == 'SYNTHETIC_HOLDOUT_LABEL_UPDATE_REPRODUCED'
    assert snapshot(root) == after


@pytest.mark.parametrize('target', ['request', 'continuation', 'daily_export'])
def test_preview_does_not_authorize_changed_input_publication(tmp_path, seed, capsys, target):
    root, request = fixture(tmp_path, seed)
    name = write(root, request)
    assert update.main(['--bundle-root', str(root), '--preview', name]) == 0
    assert json.loads(capsys.readouterr().out)['published'] is False
    changed = root / (name if target == 'request' else request[target])
    changed.write_bytes(changed.read_bytes() + b' ')
    before = snapshot(root)
    with pytest.raises(SystemExit) as failure:
        update.main(['--bundle-root', str(root), '--request', name])
    assert failure.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == '' and 'refused or incomplete' in captured.err
    assert snapshot(root) == before


def test_incomplete_companion_is_preserved_and_retry_refuses(tmp_path, seed, monkeypatch, capsys):
    root, request = fixture(tmp_path, seed)
    name = write(root, request)
    publisher = update.publish_research_text
    interrupted = []

    def partial(destination, text, **kwargs):
        if json.loads(text).get('schema') == 'ATLAS_SYNTHETIC_HOLDOUT_UPDATE_RESULT_V1':
            raw = text.encode('utf-8')
            path = destination / (hashlib.sha256(raw).hexdigest() + '.json')
            with path.open('xb') as handle:
                handle.write(raw[:16])  # Synthetic interrupted publication, never production state.
            interrupted.append(path)
            raise OSError('synthetic interrupted write')
        return publisher(destination, text, **kwargs)

    monkeypatch.setattr(update, 'publish_research_text', partial)
    with pytest.raises(SystemExit) as failure:
        update.main(['--bundle-root', str(root), '--request', name])
    assert failure.value.code == 2 and capsys.readouterr().out == ''
    assert len(interrupted) == 1 and len(interrupted[0].read_bytes()) == 16
    before = snapshot(root)
    monkeypatch.setattr(update, 'publish_research_text', publisher)
    with pytest.raises(SystemExit) as retry:
        update.main(['--bundle-root', str(root), '--request', name])
    assert retry.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == '' and 'refused or incomplete' in captured.err
    assert snapshot(root) == before
