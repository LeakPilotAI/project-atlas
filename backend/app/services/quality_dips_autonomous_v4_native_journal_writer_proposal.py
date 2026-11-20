"""Confined native append-only V4 journal proposal; no operational authority.

Writes RESERVED and COMMITTED snapshots to distinct immutable native files.
Never overwrites a snapshot, reuses a name, self-issues custody pins or
resumes an uncertain reservation. Caller must provide trusted external pins.
"""
from app.services.paper_financial_replay import body, strict
from app.services.quality_dips_autonomous_v4_native_journal_recovery_proposal import inspect_pinned_native_v4_journal
from app.services.quality_dips_autonomous_v4_publication_journal_proposal import (
    initial_publication_journal, transition_publication_journal)


class ConfinedNativeV4JournalProposal:
    def __init__(self, native, pins=None):
        if (not callable(getattr(native, 'write_bound', None))
                or not callable(getattr(native, 'read_bound', None))
                or not callable(getattr(native, 'list_names', None))):
            raise ValueError('V4_NATIVE_JOURNAL_PORT_REQUIRED')
        if pins is not None and (type(pins) is not dict or pins):
            raise ValueError('V4_NATIVE_JOURNAL_RECOVERY_NOT_AUTHORIZED')
        if native.list_names():
            raise ValueError('V4_NATIVE_JOURNAL_EXISTING_FILES_REFUSED')
        self.native = native
        self.pins = {}
        self.state = initial_publication_journal()
        self.fenced = False

    def _append(self, name, state):
        if self.fenced:
            raise ValueError('V4_NATIVE_JOURNAL_APPEND_FENCED')
        try:
            if name in self.pins or set(self.native.list_names()) != set(self.pins):
                raise ValueError('V4_NATIVE_JOURNAL_APPEND_FENCED')
            self._verify_all()
            pin = self.native.write_bound(name, body(state).encode('utf-8'))
            self.pins[name] = pin
            self.state = state
            self._verify_all()
        except Exception:
            self.fenced = True
            if state['status'] == 'RESERVED':
                self.state = transition_publication_journal(state, 'RESTART')
            elif self.state['status'] == 'RESERVED':
                self.state = transition_publication_journal(self.state, 'RESTART')
            raise
        self.state = state
        return dict(pin)

    def _verify_all(self):
        if set(self.native.list_names()) != set(self.pins):
            raise ValueError('V4_NATIVE_JOURNAL_ROSTER_CHANGED')
        for name, pin in self.pins.items():
            raw = self.native.read_bound(name, pin)
            if type(raw) is not bytes or len(raw) > 65536:
                raise ValueError('V4_NATIVE_JOURNAL_NATIVE_READ_INVALID')
            doc = strict(raw.decode('utf-8'))
            if type(doc) is not dict or body(doc).encode('utf-8') != raw:
                raise ValueError('V4_NATIVE_JOURNAL_NONCANONICAL')
            transition_publication_journal(doc, 'RESTART')
        if set(self.native.list_names()) != set(self.pins):
            raise ValueError('V4_NATIVE_JOURNAL_POST_READ_ROSTER_CHANGED')
        if self.pins:
            inspected = inspect_pinned_native_v4_journal(self.native, self.pins)
            if (inspected['revision'] != self.state['revision']
                    or inspected['head'] != self.state['head']
                    or inspected['status'] != ('UNCERTAIN' if self.state['status'] == 'RESERVED' else 'IDLE')):
                raise ValueError('V4_NATIVE_JOURNAL_REPLAY_STATE_MISMATCH')

    def reserve(self, record):
        if self.fenced or self.state['status'] != 'IDLE':
            raise ValueError('V4_NATIVE_JOURNAL_NOT_IDLE')
        next_state = transition_publication_journal(self.state, 'RESERVE', record)
        return self._append(f"{next_state['pending']['revision']:04d}-reserved.json", next_state)

    def commit(self):
        if self.fenced or self.state['status'] != 'RESERVED':
            raise ValueError('V4_NATIVE_JOURNAL_NOT_RESERVED')
        next_state = transition_publication_journal(self.state, 'COMMIT')
        return self._append(f"{next_state['revision']:04d}-committed.json", next_state)

    def restart(self):
        self.fenced = True
        self.state = transition_publication_journal(self.state, 'RESTART')
        return {**self.state, 'operational_authority_accepted': False,
                'paper_execution_authorized': False, 'live_order_authorized': False}