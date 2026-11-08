# AIP-06 source-only batch checkpoint — November 5, 2026

Status: SOURCE CONTRACT INCREMENT; PHYSICAL ASSEMBLY BLOCKED. AIP-06 remains 5/18, PAPER NO, production NO-GO. This checkpoint does not supersede the authorization packet or any B1/C1/D1/E1 gate, 21 commissioning decisions, native refusal, or single-use approval requirements.

## Source work

- `CaseContext.physical_host_handoff` creates a defensive data-only copy from an original held reservation, with a deterministic integrity digest. The digest detects accidental/unchecked mutation; it is **not** a keyed signature, authorization credential, native attestation or replacement for authenticated private transport.
- `verify_physical_host_handoff` checks closed schema/integrity, exact inherited case/role/source scope, matching scenario/case/manifest/evidence, held Stop reserve, and the original still-open shared-ledger directory owned by the parent. It does not import handles, launch a host, or grant execution.
- `prepare_reader_from_provider` requires an explicit typed `WindowsReaderSet` and `PinnedWindowsRead` pair before entering the existing independently guarded reader preparation path. The default reader entry remains refusal-only.
- Tests cover missing OWNERSHIP-PROBES producer, missing/invalid host reservations, copy isolation, damaged handoffs, original resource release, unqualified reader provider pairs, and existing refusal paths.

## Remaining work, dependency order

1. Bind a genuinely separate case-host to the original retained guarded process/session, private descriptor and inherited scope. Prove prospective allocation and original-handle/Job ownership without controller-interpreter execution of guard-installing cases.
2. Construct the real independent reader provider host with native handle import/duplication, authenticated framed exchange, NativeIO failed-open escrow and complete terminal release. Current source tests use injected OS/IPC.
3. Connect one existing OWNERSHIP-PROBES native producer end-to-end, then F05/F06/F09/F11/F12/bootstrap-IPC and the remaining reviewed case bindings. Preserve their original fault semantics and budget.
4. Resolve Proactor/socketpair compatibility without changing no-network policy. Collect actual Windows identity, ACL, Job, socket, capacity, Stop and source-origin evidence under approved technical scope.
5. Only after independent technical review, request fresh single-use native authorization; complete native acceptance and separate PAPER commissioning. No live trading or autostart.

## Validation and source control

Focused scoped-context suite: 98 passed, 0 failed (17.36s). Combined scoped-context and Windows-adapter suite: 186 passed, 0 failed (21.74s). Additional acceptance-control/ownership-probes/controller-contract regression: 178 passed, 0 failed (7.66s). These suites may overlap; counts must not be added as distinct tests. Unrelated pre-existing `tests/test_free_research_pipeline.py` modification remains excluded from this batch. No Genesis, account, provider, financial worker, Discord, live/PAPER operation, or native acceptance was launched by these source changes.
