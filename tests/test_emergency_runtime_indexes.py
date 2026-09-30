import json

from app.investment.latest_index import LatestIndex
from app.services.runtime_hardening import stream_jsonl


def test_latest_index_incremental_partial_tail_and_timestamp(tmp_path):
    path = tmp_path / 'opportunities.jsonl'
    path.write_text(json.dumps({'symbol': 'A', 'timestamp': '2026-02'}) + '\n')
    index = LatestIndex()
    assert index.read(path)[0]['timestamp'] == '2026-02'
    assert index.read(path)[0]['symbol'] == 'A'
    assert index.parsed_rows == 1
    with path.open('a') as f:
        f.write(json.dumps({'symbol': 'A', 'timestamp': '2026-01'}) + '\n')
        f.write('{"symbol":"B"')
    assert len(index.read(path)) == 1
    with path.open('a') as f:
        f.write('}\n')
    assert len(index.read(path)) == 2
    assert index.parsed_rows == 3
    assert index.read(path)[0]['timestamp'] == '2026-02'
    path.write_text('{"symbol":"C"}\n')
    assert index.read(path) == [{'symbol': 'C'}]


def test_plan_index_preserves_last_append_and_does_not_retain_history(tmp_path):
    path = tmp_path / 'plans.jsonl'
    path.write_text(''.join(json.dumps({'symbol': 'A', 'value': i}) + '\n' for i in range(1000)))
    index = LatestIndex()
    assert index.read(path) == [{'symbol': 'A', 'value': 999}]
    assert len(index.files[path.resolve()]['rows']) == 1


def test_latest_index_replacement_regrowth_empty_malformed_and_caller_mutation(tmp_path):
    path = tmp_path / 'opportunities.jsonl'
    path.touch()
    index = LatestIndex()
    assert index.read(path) == []
    path.write_text('{"symbol":"A","nested":{"v":1}}\n')
    rows = index.read(path)
    rows[0]['nested']['v'] = 99
    assert index.read(path)[0]['nested']['v'] == 1
    path.write_text('{"symbol":"NEW","nested":{"v":2},"padding":"longer file"}\ninvalid\n')
    assert [r['symbol'] for r in index.read(path)] == ['NEW']
    replacement = tmp_path / 'replacement'
    replacement.write_text('{"symbol":"ROTATED"}\n')
    replacement.replace(path)
    assert index.read(path) == [{'symbol': 'ROTATED'}]
    assert LatestIndex().read(path) == index.read(path)


def test_stream_reader_is_lazy_and_preserves_malformed_rows(tmp_path):
    path = tmp_path / 'rows.jsonl'
    path.write_bytes(b'{"event":"open"}\n\xff\n{"event":"close"}\n')
    rows = stream_jsonl(path)
    assert iter(rows) is rows
    assert next(rows) == {'event': 'open'}
    assert next(rows)['event'] == '_malformed'
    assert next(rows) == {'event': 'close'}


def test_daily_history_reuses_unchanged_file_and_invalidates_append(tmp_path, monkeypatch):
    from app.investment import history
    path = tmp_path / 'A.jsonl'
    path.write_text('{"date":"2026-01-01","close":1}\n')
    original = history._read_bars
    calls = []
    def read(*args):
        calls.append(1)
        return original(*args)
    monkeypatch.setattr(history, '_read_bars', read)
    assert len(history.load_bars('A', tmp_path)) == 1
    history.load_bars('A', tmp_path)[0].close = 999
    assert history.load_bars('A', tmp_path)[0].close == 1
    assert len(history.load_bars('A', tmp_path)) == 1
    assert len(calls) == 1
    with path.open('a') as f:
        f.write('{"date":"2026-01-02","close":2}\n')
    assert len(history.load_bars('A', tmp_path)) == 2
    assert len(calls) == 2
