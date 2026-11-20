# E136 consent-bound delivery prototype contract

This document defines the isolated prototype used to test fail-closed dispatch gating without altering the live production outbox schema or production producer wiring.

## Contract

1. Immutable recipient consent-generation binding
   - Every queued delivery records the recipient ID, the consent generation at the time it was admitted, and the consent database identity.
   - Delivery admission fails if any of those values are missing or if the current consent state no longer matches the bound generation.

2. Consent database identity
   - A queue record is only valid when `consent_database_id == coordinator.consent.database_id`.
   - A mismatched identity immediately denies admission and causes future dispatch attempts to fail closed.

3. Queue admission
   - A delivery may enter the queue only after a fresh authorization check confirms the recipient is currently subscribed at the recorded generation and the witness evidence still matches.
   - If the queue record was created under an older generation, it cannot be reactivated by a later resubscription.

4. Revocation and resubscription
   - Revocation invalidates the old generation immediately.
   - A later resubscription creates a new generation, but it never reactivates deliveries that were queued under the older generation.

5. Stale or missing generations
   - Missing, non-positive, or stale generation values are treated as denial.
   - The system never authorizes based on a historical generation once the current ledger has moved beyond it.

6. Legacy deliveries without consent evidence
   - Legacy queue records without a stored generation or database identity are denied by default.
   - This prototype treats them as untrusted and leaves them in a fail-closed state.

7. Crash recovery and ambiguous transport outcomes
   - The prototype stores the authorization metadata at queue-admission time and re-validates it before transport.
   - Ambiguous outcomes are recorded as `uncertain` and are not automatically re-authorized.
   - The design requires a fresh authorization decision before any later retry.

8. Concurrent dispatch workers
   - Each worker rechecks the stored queue record against the current consent state before sending.
   - The queue database is isolated from production, so there is no production safety dependency on a shared network-dependent transport path.

9. Authorization-to-transport admission ordering
   - Authorization must precede transport admission; the adapter performs a fresh authorization check immediately before invoking the fake sender.
   - A network request already in-flight is outside the scope of any local SQLite authorization fence; this prototype cannot guarantee anything about a transport request once the sender has already begun.

## Durable claim, crash, and process semantics

- SQLite commit durability is preserved only for the same local database file and only after the transactional commit completes. A row in `dispatching` state remains on disk after a process exit, so a crash is observable by the next worker process.
- The adapter now records a per-row lease token and expiration timestamp. A stale `dispatching` row with an expired lease is treated as abandoned and can be reclaimed by a fresh worker after revalidation.
- This protects against a worker dying after claim but before completion without relying on in-memory state.
- This does not provide a general distributed lease or a machine-to-machine trust boundary. It is a durable local fence only for the same SQLite file on the same host.
- Two independent worker processes can safely compete for a single queued record because the claim updates occur under `BEGIN IMMEDIATE` and row-level `WHERE ... status='queued' OR ... expired dispatching` conditions. The second process cannot claim the same row while the lease remains active.
- Once a sender has already started, no local gate can retroactively revoke or guarantee the network outcome. The transport boundary is therefore the last point at which revocation is enforced: after that boundary, we only guarantee fail-closed behavior for future sends, not for in-flight network activity.

## Guarantees

- The adapter guarantees fail-closed behavior when consent evidence is missing, stale, mismatched, or revoked.
- It guarantees that a later resubscription cannot reactivate a delivery that was queued under an older generation.
- It guarantees that historical recovery diagnostics stay diagnostic only; they are never treated as authorization.
- It guarantees that stale local lease claims can be recovered by fresh workers after the lease expires, but it does not guarantee any rollback-resistant external authority.

## Proposed migration and activation prerequisites

- A future production migration must add explicit, durable consent-generation metadata to the lifecycle outbox and require it for every dispatch admission record.
- The migration must bind each queued record to both the recipient-specific generation and the exact consent database identity that was active at queue time.
- A fresh consent authorization gate must run on every transport admission, and any queued row that lacks both values must remain blocked.
- Transport admission must use a row-claiming or lease fence so only one worker can transition a queued record into an in-flight state. Production activation is not allowed until the fence and the queue status machine are tested under concurrent workers.
- The migration must not claim rollback resistance unless it introduces a trusted external checkpoint or attestation boundary that is not just an additional local SQLite file pair.
- Safe activation requires: isolated migration rehearsal on temp databases, compatibility tests against the E133 outbox and E135 simulation producer, fail-closed handling for legacy rows, and explicit sign-off that no real Discord send remains enabled until a trusted authority is in place.
- This prototype does not perform the migration and remains intentionally isolated from the live production path.

## Limitations

- This is not a rollback-resistant authority. It relies on the local coordinator and witness SQLite ledgers as evidence, which are not a distributed or externally attested trust boundary.
- Once a network request has already started, no local gate can retroactively guarantee delivery success or prevent in-flight transport-side outcomes.
- If local evidence has been coordinatedly restored or tampered with, the adapter fails closed rather than making a delivery decision.

## Trust boundary

The isolated prototype intentionally trusts only the local coordinator/witness pair and the exact database identity recorded in the queue. It does not claim protection against coordinated local rollback or external attestation because no such authority is present in this design.
