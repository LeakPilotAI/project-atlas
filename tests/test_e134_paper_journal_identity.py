import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

from app.services import paper_journal as paper_journal_mod
from app.services.discord_lifecycle_outbox import DiscordLifecycleOutbox
from app.services.paper_journal_identity import read_paper_journal_identities

STAMP = "2026-10-14T12:00:00+00:00"


def _row(event, trade_id="trade-1", **values):
    base = {"event": event, "trade_id": trade_id, "timestamp": STAMP}
    base.update(values)
    return (json.dumps(base, separators=(",", ":")) + "\n").encode()


def _write(path, *rows):
    path.write_bytes(b"".join(rows))


def test_duplicate_source_rows_have_stable_but_distinct_ids(tmp_path):
    path = tmp_path / "paper.jsonl"
    open_row = _row("open")
    duplicate_mark = _row("mark", mark=101, unrealized_r=1.0)
    _write(path, open_row, duplicate_mark, duplicate_mark)

    first = read_paper_journal_identities(path)
    second = read_paper_journal_identities(path)

    assert first.reliable
    assert [event.source_sequence for event in first.events] == [1, 2, 3]
    assert first.events[1].event_id != first.events[2].event_id
    assert [event.event_id for event in first.events] == [
        event.event_id for event in second.events
    ]


def test_multiple_marks_keep_append_order_and_unique_identity(tmp_path):
    path = tmp_path / "paper.jsonl"
    _write(
        path,
        _row("open"),
        _row("mark", mark=100.5),
        _row("mark", mark=101.0),
        _row("mark", mark=101.5),
    )
    batch = read_paper_journal_identities(path)
    assert batch.reliable
    assert [event.event_type for event in batch.events] == [
        "PAPER_ENTRY",
        "PAPER_MARK",
        "PAPER_MARK",
        "PAPER_MARK",
    ]
    assert [event.source_sequence for event in batch.events] == [1, 2, 3, 4]
    assert len({event.event_id for event in batch.events}) == 4


def test_entry_mark_close_order_is_compatible_with_e133_outbox(tmp_path):
    path = tmp_path / "paper.jsonl"
    _write(
        path,
        _row("open", entry_timestamp=STAMP),
        _row("mark", mark=101.25),
        _row("close", result="WIN", exit_reason="TARGET", exit_timestamp=STAMP),
    )
    batch = read_paper_journal_identities(path)
    assert batch.reliable
    assert [event.event_type for event in batch.events] == [
        "PAPER_ENTRY",
        "PAPER_MARK",
        "PAPER_CLOSE",
    ]

    outbox = DiscordLifecycleOutbox(tmp_path / "outbox.sqlite3")
    for event in batch.events:
        assert outbox.enqueue(event, [111])
    assert [
        state["status"]
        for event in batch.events
        for state in outbox.delivery_states(event.event_id).values()
    ] == [
        "pending",
        "pending",
        "pending",
    ]


def test_interruption_and_recovery_are_stable_across_restart(tmp_path, monkeypatch):
    journal_path = tmp_path / "paper.jsonl"
    monkeypatch.setattr(paper_journal_mod, "JOURNAL_PATH", journal_path)
    monkeypatch.setattr(
        paper_journal_mod, "CANDIDATE_PATH", tmp_path / "candidates.jsonl"
    )
    journal = paper_journal_mod.PaperJournal()
    trade_id = asyncio.run(
        journal.open_trade(
            symbol="BTC",
            side="LONG",
            entry=100,
            stop=99,
            tp1=102,
            tp2=103,
        )
    )
    journal.update_excursion(trade_id, 101.0, force=True)
    assert journal.interrupt_open_for_shutdown() == [trade_id]

    first = read_paper_journal_identities(journal_path)
    recovered = paper_journal_mod.PaperJournal()
    assert recovered.list_open() == []
    second = read_paper_journal_identities(journal_path)

    assert first.reliable and second.reliable
    assert [event.event_type for event in first.events] == [
        "PAPER_ENTRY",
        "PAPER_MARK",
        "PAPER_INTERRUPTED",
    ]
    assert [event.source_sequence for event in first.events] == [1, 2, 3]
    assert [event.event_id for event in first.events] == [
        event.event_id for event in second.events
    ]


def test_restart_rescan_preserves_outbox_deduplication(tmp_path):
    path = tmp_path / "paper.jsonl"
    _write(path, _row("open"), _row("mark", mark=100.2))
    first_batch = read_paper_journal_identities(path)
    outbox_path = tmp_path / "outbox.sqlite3"
    outbox = DiscordLifecycleOutbox(outbox_path)
    assert [outbox.enqueue(event, [111]) for event in first_batch.events] == [
        True,
        True,
    ]

    restarted_batch = read_paper_journal_identities(path)
    restarted_outbox = DiscordLifecycleOutbox(outbox_path)
    assert [event.event_id for event in restarted_batch.events] == [
        event.event_id for event in first_batch.events
    ]
    assert [
        restarted_outbox.enqueue(event, [111]) for event in restarted_batch.events
    ] == [
        False,
        False,
    ]
    with path.open("ab") as handle:
        handle.write(_row("close", result="WIN", exit_reason="TARGET"))
    appended_batch = read_paper_journal_identities(path)
    assert [event.event_id for event in appended_batch.events[:2]] == [
        event.event_id for event in first_batch.events
    ]
    assert appended_batch.events[-1].source_sequence == 3
    assert restarted_outbox.enqueue(appended_batch.events[-1], [111])


def test_concurrent_append_writers_produce_unique_ordered_ids(tmp_path):
    path = tmp_path / "paper.jsonl"
    path.write_bytes(_row("open"))
    marks = [_row("mark", mark=100 + index / 100) for index in range(40)]
    journal = paper_journal_mod.PaperJournal.__new__(paper_journal_mod.PaperJournal)
    journal._malformed_lines = []

    def append(raw):
        journal._append(path, json.loads(raw))

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(append, marks))

    batch = read_paper_journal_identities(path)
    assert batch.reliable
    assert len(batch.events) == 41
    assert [event.source_sequence for event in batch.events] == list(range(1, 42))
    assert len({event.event_id for event in batch.events}) == 41


def test_malformed_and_legacy_rows_fail_closed_without_rewriting(tmp_path):
    path = tmp_path / "paper.jsonl"
    legacy_open = _row(
        "open",
        entry_timestamp=STAMP,
        trade_type=None,
        source="older_strategy",
    )
    malformed = b'{"event":"mark","trade_id":\n'
    legacy_close = _row("close", result="WIN", exit_reason="TARGET")
    _write(path, legacy_open, malformed, legacy_close)
    original = path.read_bytes()

    batch = read_paper_journal_identities(path)
    assert not batch.reliable
    assert batch.events == ()
    assert batch.malformed_lines == 1
    assert path.read_bytes() == original


def test_valid_legacy_records_without_new_identity_fields_remain_readable(tmp_path):
    path = tmp_path / "paper.jsonl"
    _write(
        path,
        _row("open", entry_timestamp=STAMP, source="legacy", trade_type=None),
        _row("mark", mark=100.5),
        _row("close", result="STOP", exit_reason="SETUP_STOP"),
    )
    batch = read_paper_journal_identities(path)
    assert batch.reliable
    assert [event.event_type for event in batch.events] == [
        "PAPER_ENTRY",
        "PAPER_MARK",
        "PAPER_RISK_STOP",
    ]
    assert [event.source_sequence for event in batch.events] == [1, 2, 3]


def test_partial_tail_blocks_dispatch_and_recovers_at_same_identity(tmp_path):
    path = tmp_path / "paper.jsonl"
    complete_open = _row("open")
    partial_mark = (
        b'{"event":"mark","trade_id":"trade-1","timestamp":"2026-10-14T12:00:00+00:00"'
    )
    _write(path, complete_open, partial_mark)

    partial = read_paper_journal_identities(path)
    assert not partial.reliable
    assert partial.events == ()
    assert partial.has_partial_tail

    with path.open("ab") as handle:
        handle.write(b',"mark":101}\n')
    recovered = read_paper_journal_identities(path)
    repeated = read_paper_journal_identities(path)
    assert recovered.reliable
    assert [event.source_sequence for event in recovered.events] == [1, 2]
    assert [event.event_id for event in recovered.events] == [
        event.event_id for event in repeated.events
    ]


def test_unidentifiable_lifecycle_event_fails_closed(tmp_path):
    path = tmp_path / "paper.jsonl"
    _write(path, _row("open", trade_id=None))
    batch = read_paper_journal_identities(path)
    assert not batch.reliable
    assert batch.events == ()
    assert batch.invalid_lifecycle_rows == 1


def test_lifecycle_event_without_timestamp_fails_closed(tmp_path):
    path = tmp_path / "paper.jsonl"
    _write(
        path,
        _row("open", timestamp=None, entry_timestamp=None, signal_timestamp=None),
    )
    batch = read_paper_journal_identities(path)
    assert not batch.reliable
    assert batch.events == ()
    assert batch.invalid_lifecycle_rows == 1


def test_test_trades_and_non_lifecycle_rows_are_not_discord_events(tmp_path):
    path = tmp_path / "paper.jsonl"
    _write(
        path,
        _row("session_start", trade_id=None),
        _row("open", trade_id="test-1", trade_type="TEST"),
        _row("open", trade_id="paper-1"),
    )
    batch = read_paper_journal_identities(path)
    assert batch.reliable
    assert len(batch.events) == 1
    assert batch.events[0].entity_id == "paper-1"


def test_missing_journal_is_empty_and_reliable(tmp_path):
    batch = read_paper_journal_identities(tmp_path / "missing.jsonl")
    assert batch.reliable
    assert batch.events == ()
