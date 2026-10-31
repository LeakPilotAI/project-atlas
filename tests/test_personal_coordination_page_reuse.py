"""Versioned immutable page reuse; no real resources or financial authority."""
import copy
import hashlib
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import body, strict
from test_personal_native_coordination_memory import installation_authority, native_double

from scripts.observation_runtime.personal_coordination_store import PAGE


def setup(monkeypatch):
    s = native_double(monkeypatch)
    s.before = b'a' * PAGE + b'b' * PAGE + b'c' * PAGE
    s.after = b'a' * PAGE + b'B' * PAGE + b'c' * PAGE
    s.owner.initialize(s.before, authorization=SimpleNamespace(lease=installation_authority))
    s.original = copy.deepcopy(s.files)
    return s


def publish(s):
    with s.owner.transaction(readonly=False) as tx:
        tx.publish(s.before, s.after)


def rewrite(s, name, value):
    raw = body(value).encode()
    binding = {**s.files[name][1], 'sha256': hashlib.sha256(raw).hexdigest()}
    s.files[name] = raw, binding
    return copy.deepcopy(binding)


def cold_read(s):
    s.owner.known = None
    s.owner._page_cut = None
    s.owner._verified_prefix = None
    return s.owner._load()


def test_v1_predecessor_v2_reuses_only_unchanged_pages_with_all_ack_boundaries(monkeypatch):
    s = setup(monkeypatch)
    publish(s)
    assert all(s.files[name] == value for name, value in s.original.items())
    assert set(s.files) - set(s.original) == {
        '0002-intent.json', '0002-page-0002.bin', '0002-commit.json', '0002-ack.json'}
    commit = strict(s.files['0002-commit.json'][0].decode())
    assert commit['schema'] == 'PERSONAL_NATIVE_COORDINATION_COMMIT_V2'
    assert [p['name'] for p in commit['pages']] == [
        '0001-page-0001.bin', '0002-page-0002.bin', '0001-page-0003.bin']
    assert cold_read(s)[0] == s.after
    assert s.owner.remaining_commits() == 126


def test_identical_image_still_has_separate_intent_commit_ack_and_revision(monkeypatch):
    s = setup(monkeypatch)
    s.after = s.before
    publish(s)
    assert set(s.files) - set(s.original) == {'0002-intent.json', '0002-commit.json', '0002-ack.json'}
    assert cold_read(s)[0] == s.before
    assert s.owner.remaining_commits() == 126


@pytest.mark.parametrize('length', [1, PAGE-1, PAGE, PAGE+1, 2*PAGE+1, 4*PAGE])
def test_shrink_expand_and_partial_pages_replay_exact_bytes(monkeypatch, length):
    s = setup(monkeypatch)
    s.after = (s.before + b'd' * PAGE)[:length]
    publish(s)
    assert cold_read(s)[0] == s.after
    assert all(s.files[name] == value for name, value in s.original.items())


@pytest.mark.parametrize('leaf', ['0002-intent.json', '0002-page-0002.bin', '0002-commit.json', '0002-ack.json'])
def test_interrupted_v2_publication_is_unknown_not_success_or_retry(monkeypatch, leaf):
    s = setup(monkeypatch)
    s.owner.fail_leaf = leaf
    with pytest.raises(OSError, match='INTERRUPTED'):
        publish(s)
    assert s.owner.poisoned and 'unknown.json' in s.files
    assert all(s.files[name] == value for name, value in s.original.items())
    s.owner.poisoned = False  # Fresh observer model; the durable latch still refuses.
    with pytest.raises(ValueError, match='NAMESPACE'):
        cold_read(s)
    with pytest.raises(ValueError):
        publish(s)


@pytest.mark.parametrize('damage', ['future', 'different_index', 'foreign_name', 'wrong_binding',
                                   'missing_binding', 'duplicate_page', 'unsupported_schema'])
def test_forged_commit_and_matching_ack_cannot_hide_invalid_page_references(monkeypatch, damage):
    s = setup(monkeypatch)
    publish(s)
    commit = strict(s.files['0002-commit.json'][0].decode())
    if damage == 'future': commit['pages'][0]['name'] = '0003-page-0001.bin'
    if damage == 'different_index': commit['pages'][0] = copy.deepcopy(commit['pages'][2])
    if damage == 'foreign_name': commit['pages'][0]['name'] = '..\\foreign.bin'
    if damage == 'wrong_binding': commit['pages'][0]['binding']['id'][-1] += 1
    if damage == 'missing_binding': del commit['pages'][0]['binding']
    if damage == 'duplicate_page': commit['pages'][1] = copy.deepcopy(commit['pages'][0])
    if damage == 'unsupported_schema': commit['schema'] = 'PERSONAL_NATIVE_COORDINATION_COMMIT_V999'
    binding = rewrite(s, '0002-commit.json', commit)
    ack = strict(s.files['0002-ack.json'][0].decode())
    ack['commit'] = binding
    rewrite(s, '0002-ack.json', ack)
    with pytest.raises(ValueError):
        cold_read(s)


def test_tampered_reused_immutable_bytes_refuse_and_cannot_be_repaired_by_replay(monkeypatch):
    s = setup(monkeypatch)
    publish(s)
    raw, binding = s.files['0001-page-0001.bin']
    s.files['0001-page-0001.bin'] = b'X' + raw[1:], binding
    with pytest.raises(ValueError, match='DIGEST'):
        cold_read(s)


def test_stale_cas_cannot_publish_after_other_commit(monkeypatch):
    s = setup(monkeypatch)
    publish(s)
    before = copy.deepcopy(s.files)
    with pytest.raises(ValueError, match='STALE_CAS'), s.owner.transaction(readonly=False) as tx:
        tx.publish(s.before, b'conflicting mutation')
    assert s.files == before


def test_full_image_digest_and_ack_still_required(monkeypatch):
    s = setup(monkeypatch)
    publish(s)
    ack = strict(s.files['0002-ack.json'][0].decode())
    ack['image_digest'] = '0' * 64
    rewrite(s, '0002-ack.json', ack)
    with pytest.raises(ValueError, match='ACK_UNKNOWN'):
        cold_read(s)


def test_older_same_index_page_is_not_the_current_predecessor(monkeypatch):
    s = setup(monkeypatch)
    publish(s)
    with s.owner.transaction(readonly=False) as tx:
        tx.publish(s.after, s.after[:-1]+b'Z')
    commit = strict(s.files['0003-commit.json'][0].decode())
    commit['pages'][1] = {'name': '0001-page-0002.bin', 'binding': s.original['0001-page-0002.bin'][1]}
    binding = rewrite(s, '0003-commit.json', commit)
    ack = strict(s.files['0003-ack.json'][0].decode())
    ack['commit'] = binding
    rewrite(s, '0003-ack.json', ack)
    with pytest.raises(ValueError, match='FOREIGN_PAGE_REFERENCE'):
        cold_read(s)


def test_commit_before_ack_without_failure_latch_still_refuses_after_restart(monkeypatch):
    s = setup(monkeypatch)
    publish(s)
    del s.files['0002-ack.json']  # Synthetic crash cut before ACK creation, not repair.
    with pytest.raises(ValueError, match='INCOMPLETE_UNKNOWN'):
        cold_read(s)
