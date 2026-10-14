"""E135 simulation-only integration; no production paths, hooks, or transport.

Only new trades opened after an explicit durable watermark are eligible. Historical
trades stay excluded, so E134's original sequence can satisfy E133 without rebasing.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
import tempfile
import threading
from contextlib import contextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from app.alerts.subscriptions import DiscordSubscriptionStore
from app.services.discord_lifecycle_outbox import (
    DiscordLifecycleOutbox,
    LifecycleContractError,
    LifecycleEvent,
)
from app.services.paper_journal_identity import read_paper_journal_identities


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _identity(path: Path) -> list[int]:
    stat = path.stat()
    return [stat.st_dev, stat.st_ino]


class IsolatedPaperLifecycleProducer:
    """Explicitly invoked prototype. Its storage must be a dedicated OS-temp directory.

    The durable staging transaction freezes recipients alongside the read cursor.
    A crash before outbox enqueue replays staging, not source selection or recipients.
    E133 dedup makes the second transaction replay-safe. No worker is started here.
    """

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        temp = Path(tempfile.gettempdir()).resolve()
        if self.root.parent != temp or not self.root.name.startswith("atlas-e135-"):
            raise LifecycleContractError("E135 requires a dedicated atlas-e135- OS-temp directory")
        if not self.root.is_dir():
            raise LifecycleContractError("simulation directory must already exist")
        self.journal = self.root / "synthetic-paper.jsonl"
        self.subscriptions = self.root / "synthetic-subscribers.json"
        self.state_path = self.root / "producer.sqlite3"
        self.outbox_path = self.root / "outbox.sqlite3"
        self._stopped = threading.Event()
        self._check_paths()
        with self._transaction() as db:
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if not tables and version == 0:
                db.execute("CREATE TABLE state (id INTEGER PRIMARY KEY CHECK(id=1), document TEXT NOT NULL)")
                db.execute("CREATE TABLE staged (offset INTEGER PRIMARY KEY, event_id TEXT UNIQUE NOT NULL, event TEXT NOT NULL, recipients TEXT NOT NULL, consent TEXT NOT NULL)")
                db.execute("PRAGMA user_version=1")
            elif tables != {"state", "staged"} or version != 1:
                raise LifecycleContractError("unrecognized producer database; no reset allowed")
            if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise LifecycleContractError("producer database integrity failure")
        self.outbox = DiscordLifecycleOutbox(self.outbox_path)

    def _check_paths(self):
        for path in (self.journal, self.subscriptions, self.state_path, self.outbox_path):
            if path.resolve().parent != self.root:
                raise LifecycleContractError("simulation paths cannot escape their directory")

    @contextmanager
    def _transaction(self):
        self._check_paths()
        db = sqlite3.connect(self.state_path, timeout=10, isolation_level=None)
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _read_source(self):
        self._check_paths()
        before = self.journal.stat()
        raw = self.journal.read_bytes()
        batch = read_paper_journal_identities(self.journal)
        after = self.journal.stat()
        signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
        if signature(before) != signature(after) or len(raw) != before.st_size or not batch.reliable:
            raise LifecycleContractError("journal changed, incomplete, or unreliable; no cursor advance")
        return raw, batch, [before.st_dev, before.st_ino]

    def _consent(self):
        self._check_paths()
        # Missing store is not an implicit owner opt-in. No legacy owner fallback.
        if not self.subscriptions.exists():
            return [], {"exists": False}
        before = self.subscriptions.stat()
        if before.st_size > 65536:
            raise LifecycleContractError("subscription snapshot exceeds 64 KiB")
        raw = self.subscriptions.read_bytes()
        store = DiscordSubscriptionStore(self.subscriptions)
        after = self.subscriptions.stat()
        signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
        if not store.reliable or signature(before) != signature(after):
            raise LifecycleContractError("subscription snapshot unreliable")
        return sorted(store.subscriber_ids), {
            "exists": True, "identity": [before.st_dev, before.st_ino],
            "mtime": before.st_mtime_ns, "hash": _digest(raw),
        }

    @staticmethod
    def _state(db):
        row = db.execute("SELECT document FROM state WHERE id=1").fetchone()
        if row is None:
            raise LifecycleContractError("explicit durable activation watermark required")
        state = json.loads(row[0])
        if state.get("version") != 1 or not state.get("activation_approval"):
            raise LifecycleContractError("invalid activation watermark")
        return state

    @staticmethod
    def _verify(state, raw, identity):
        if (identity != state["journal_identity"] or len(raw) < state["cursor"]
                or _digest(raw[:state["cursor"]]) != state["prefix_sha256"]):
            raise LifecycleContractError("journal truncation, replacement or rewrite; manual review required")

    @staticmethod
    def _save(db, state):
        db.execute("INSERT OR REPLACE INTO state VALUES (1, ?)", (json.dumps(state, sort_keys=True),))

    def activate_for_simulation(self, *, approval_reference: str):
        """Explicit fixture-only activation at EOF; never auto-initialized by process()."""
        if not isinstance(approval_reference, str) or not approval_reference.strip():
            raise LifecycleContractError("explicit activation approval reference required")
        with self._transaction() as db:
            if db.execute("SELECT 1 FROM state").fetchone():
                raise LifecycleContractError("activation already exists; cannot reset watermark")
            raw, batch, identity = self._read_source()
            self._save(db, {
                "version": 1, "activation_approval": approval_reference,
                "activated_at": datetime.now(UTC).isoformat(),
                "activation_offset": len(raw), "cursor": len(raw),
                "prefix_sha256": _digest(raw), "journal_identity": identity,
                "outbox_identity": _identity(self.outbox_path),
                "excluded_trades": sorted({event.entity_id for event in batch.events}),
                "delivery_approval": None,
            })

    def approve_simulated_delivery(self, *, approval_reference: str):
        if not isinstance(approval_reference, str) or not approval_reference.strip():
            raise LifecycleContractError("explicit delivery approval reference required")
        with self._transaction() as db:
            state = self._state(db)
            state["delivery_approval"] = approval_reference
            self._save(db, state)

    def process(self) -> int:
        """Freeze new eligible events/recipients atomically, then transfer idempotently."""
        if self._stopped.is_set():
            raise LifecycleContractError("producer stopped")
        with self._transaction() as db:
            state = self._state(db)
            raw, batch, identity = self._read_source()
            self._verify(state, raw, identity)
            if _identity(self.outbox_path) != state["outbox_identity"]:
                raise LifecycleContractError("outbox replaced; manual recovery required")
            recipients, consent = self._consent()
            added = 0
            for event in batch.events:
                offset = int(event.source_event_id.rsplit(":", 1)[1])
                if offset < state["cursor"] or event.entity_id in state["excluded_trades"]:
                    continue
                if event.source_sequence == 1 and event.event_type != "PAPER_ENTRY":
                    raise LifecycleContractError("post-activation orphan lifecycle event")
                db.execute("INSERT INTO staged VALUES (?, ?, ?, ?, ?)", (
                    offset, event.event_id, json.dumps(asdict(event)),
                    json.dumps(recipients), json.dumps(consent, sort_keys=True),
                ))
                added += 1
            state.update(cursor=len(raw), prefix_sha256=_digest(raw))
            self._save(db, state)
        # Recovery always replays the original staging snapshot, including empty
        # recipient sets. Never resnapshot subscriptions after partial transfer.
        with self._transaction() as db:
            rows = db.execute("SELECT event, recipients FROM staged ORDER BY offset").fetchall()
        for event, recipients in rows:
            if self._stopped.is_set():
                break
            self.outbox.enqueue(LifecycleEvent(**json.loads(event)), json.loads(recipients))
        return added

    def stop(self):
        """Stop future admission/sends; do not delete durable work or cancel the runtime."""
        self._stopped.set()

    async def dispatch_simulated(self, *, sender, now=None):
        """Fake recipient-scoped transport only; subscription changes quarantine old work.

        Any store change invalidates previous consent snapshots, even unsubscribe
        followed by resubscribe. E132 has no consent epochs, so this intentionally
        also quarantines old work after unrelated subscription changes.
        """
        if getattr(sender, "simulation_only", None) is not True:
            raise LifecycleContractError("only an explicit simulation transport is accepted")

        def authorize(event=None, recipient=None):
            if self._stopped.is_set():
                raise LifecycleContractError("producer stopped")
            with self._transaction() as db:
                state = self._state(db)
                if not state.get("delivery_approval"):
                    raise LifecycleContractError("explicit simulated delivery approval required")
                raw, _, identity = self._read_source()
                self._verify(state, raw, identity)
                if _identity(self.outbox_path) != state["outbox_identity"]:
                    raise LifecycleContractError("outbox replaced; manual recovery required")
                if event is not None:
                    row = db.execute("SELECT consent, recipients FROM staged WHERE event_id=?", (event.event_id,)).fetchone()
                    recipients, consent = self._consent()
                    if (row is None or json.loads(row[0]) != consent
                            or recipient not in recipients or recipient not in json.loads(row[1])):
                        raise LifecycleContractError("recipient consent changed; operator review required")
                    return consent

        await asyncio.to_thread(authorize)

        async def guarded_sender(*, recipient_id, event):
            expected_consent = await asyncio.to_thread(authorize, event, recipient_id)
            # Recheck after the worker yield, immediately before transport entry.
            recipients, current_consent = self._consent()
            if current_consent != expected_consent or recipient_id not in recipients:
                raise LifecycleContractError("recipient consent changed before transport entry")
            if self._stopped.is_set():
                raise LifecycleContractError("producer stopped")
            return await sender(recipient_id=recipient_id, event=event)

        try:
            return await self.outbox.dispatch_due(sender=guarded_sender, now=now)
        except asyncio.CancelledError:
            self.stop()
            # E133's lease expires into uncertain, never an automatic resend.
            raise
