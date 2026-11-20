# R7E46O research journal integrity and offline migration

Production activation and runtime restart remain prohibited in this milestone.
No production journal, commitment or migration is created by these source changes.

The append-only research JSONL has an independent sibling
`.jsonl.commitment.sqlite3` witness. A Windows byte-range lock serializes writers
and migration across both files. SQLite synchronous FULL commits a pending intent
containing target byte length and SHA-256 BEFORE the JSONL append; the collector
then appends, flushes/fsyncs, verifies exact target bytes and durably acknowledges
the commitment. A valid journal must match the independently persisted length,
digest, canonical absolute path, schema version and nonpending state. A checksum
inside each record or a newline alone is not the integrity authority.

Missing whole rows, zero-byte truncation, complete journal deletion, valid-JSON
replacement, same-length alteration, duplicate persisted records, malformed records,
missing/corrupt witness and interrupted transactions block collection without
reconstruction. An incoming duplicate with changed price/source/session raises
an explicit integrity error, preserving the original observation. Retrieving the
same original quote again after a later retrieval time remains an ordinary duplicate.
No conflicting quote is silently substituted or appended.

A crash before pending intent is committed leaves the previous committed state.
A crash after intent and before acknowledgement leaves a quarantined pending pair,
even if the append completed. This deliberately sacrifices automatic availability
rather than guessing which write completed. SQLite's transaction recovery remains
its normal atomic recovery; there is no application-level automatic blessing,
journal rewrite, truncation or retry of an uncertain append.

## Legacy compatibility and non-destructive migration

Existing nonempty OR empty JSONL without a witness is NOT adopted automatically.
Before any future separately approved migration:
1. Confirm all relevant Atlas writers are stopped through verified ownership and
   an approved maintenance window. No stop is authorized by this document.
2. Preserve immutable byte-for-byte journal backups, metadata and SHA-256 outside
   the working pair; inventory any existing witness and SQLite side files. Never
   delete or replace an existing witness to make migration pass.
3. Review the entire legacy journal and its independent historical evidence.
   Migration cannot prove that rows were not already lost before adoption. Record
   this limitation and the operator's explicit scope acceptance.
4. On an isolated COPY, instantiate `ExtendedHoursCollector` and call
   `adopt_legacy_journal(expected_sha256=<reviewed original SHA-256>)`. This explicit
   utility validates schema and complete line boundaries, holds the normal lock,
   checks the original hash, creates the witness exclusively, and leaves JSONL
   bytes unchanged. Wrong hash, malformed journal or existing witness fails closed.
5. Verify duplicate restart, exact original bytes and witness integrity on the copy.
   Only a separate operator-approved operation may apply the reviewed migration to
   production. No CLI startup path or service invokes this utility.

New journals initialize an empty commitment only if BOTH journal and witness are
absent. The witness remains bound to its original absolute path. Moving a pair to
another path is not accepted automatically; test verification copies must retain
path semantics or be explicitly migrated from reviewed legacy copies. Deployment
must preserve the original production path and must exclude all production state
from source archives.

## Failure recovery

On any integrity error preserve journal, witness, SQLite recovery files, locks and
logs. Stop further feature attempts only through an independently approved owned
lifecycle action; never kill, delete, truncate, rename, reset the witness, or bypass
locks to clear an error. Pending-intent acceptance has no automatic repair API.

For a committed witness and damaged journal, an operator-reviewed immutable journal
backup can be restored to a separate forensic copy and verified against the exact
original commitment. A fixture test demonstrates this verified-original restoration.
An eventual production restoration requires a separate procedure, verified writer
absence, backup of the damaged pair, and explicit approval. Never construct prices
or missing rows from expectations. For pending intents, missing/corrupt witnesses,
path changes or absent independent backups, remain BLOCKED and prepare a specific
forensic recovery plan; do not automatically finalize or clear pending state.

## Trust and capacity limits

The witness is independent of journal bytes, not a protection against privileged
coordinated rollback/deletion of BOTH files, tampering with the witness, disk loss,
or dishonest source data. Host access control and independent immutable backups
remain required. Treat any known restore/rollback as an operator event requiring
external evidence. No local algorithm can distinguish a brand-new store from loss
of every independent record. No HMAC key or production secret is introduced.

Journal replay/hashing and SQLite/file fsync run off the event loop and under the
same bounded acquisition lock. Underlying filesystem hangs are not forcibly killed;
provider threads already dispatched can outlive coroutine cancellation. Historical
soaks do not prove this new paired-write protocol's real production timing. Shared
provider concurrency and gaming/shutdown resource acceptance remain future gates.
