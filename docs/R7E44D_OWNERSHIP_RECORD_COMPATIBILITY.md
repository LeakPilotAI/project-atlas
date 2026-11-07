# R7E44D — ownership record compatibility repair

**PASS: scoped source repair and isolated regressions. Runtime acceptance remains pending.**

Date: 2026-10-16 (America/Chicago, CDT, UTC−05:00). Final preservation verification
at 08:51:21 UTC / 03:51:21 CDT. Branch: `chatgpt/atlas-rebuild-v1`;
HEAD: `f9df47b4cd80dd647d85043aba617cf00c4e6dc0`, unchanged.

## Root cause and call paths

The R7E44C recorded process identities matched. Its failure was a representation
error, not evidence of a foreign process or mismatched creation time.
`Invoke-BackgroundWorker` builds its owner record as a PowerShell Hashtable and
calls `Test-AtlasApiProcessOwnership`. The verifier uses
`$Owner.PSObject.Properties["launcher_pid"]`; Hashtable entries do not appear in
that property collection. The verified base-interpreter API child consequently
appeared to have no recorded launcher and was rejected. The equivalent persisted
JSON object exposes the field and passed. Timestamp-property lookup has the same
representation issue for both owner and runtime dictionaries.

The startup-error cleanup path also matters:
`Stop-OwnedApi` → `Test-VerifiedApiIdentity` → `Test-AtlasApiProcessOwnership`.
`Test-VerifiedApiIdentity` discovers the launcher before calling the shared helper.
Fixing only the helper would leave that caller unable to discover the launcher.

## Smallest repair and guarantees

- `scripts/windows/Atlas-ProcessOwnership.psm1`: normalize supplied Owner and Runtime
  records implementing IDictionary to PSCustomObject at the verifier boundary.
- `scripts/windows/Atlas-Background.ps1`: normalize the supplied Owner at the
  cleanup identity-reader boundary, before launcher discovery.
- `tests/test_r7e44d_ownership_record_compatibility.py`: isolated regression matrix.
- This report and an appended checkpoint in the full canonical roadmap.

Only three conditional representation conversions were added to production source;
all pre-existing field validation and identity branches remain unchanged. This does
not supply missing values, alter persisted records, reconstruct manifests, or add
an acceptance fallback. PID/run/root checks, exact API and launcher creation-time
checks, permitted executable checks, root-qualified uvicorn command checks, exact
recorded launcher command comparison, and parent/launcher relationships retain
their existing semantics. Existing runtime-start tolerance (30 seconds) and owner
timestamp fallback (120 seconds) now use the same supplied evidence for dictionaries
and persisted objects. A 60-second runtime skew is rejected in either representation.
Missing or malformed evidence remains fail closed. Recovery and lifecycle locks,
stale-owner handling, missing-manifest handling, and trading authority were untouched.

## Validation

**91 passed, 0 failed in 112.98 seconds.** Selection:

```
tests/test_r7e44d_ownership_record_compatibility.py
tests/test_r7e44a_ownership_audit.py
tests/test_a23_background_recovery_hardening.py
tests/test_e128_background_mode.py
tests/test_desktop_operator_hardening.py
tests/test_a23_stop_worker_failure.py
```

The 30 new parametrized tests cover 360 fixture decisions: Hashtable, ordered
dictionary, and JSON-round-tripped persisted owner objects; dictionary and persisted
runtime records; shared verifier and actual extracted cleanup-reader function.
They cover valid records, missing mandatory evidence, incorrect run/PID/root,
API and launcher PID reuse, creation-time mismatch, executable/command mismatch,
foreign processes, wrong parent, malformed PID/time, missing runtime/API/launcher,
and timestamp-source behavior. They also verify inputs are not mutated. Existing
regressions cover stale records, missing manifests, recovery locks and worker failures.
Temporary process fixtures replace all process/listener lookups; no real lifecycle
command is executed. Tests run against source copies with production data access
and external networking blocked by the isolated runner.

The original R7E44C fixture-only reproducer now exits **0**, reporting Hashtable
TRUE and PSCustomObject TRUE. Its original failure evidence was retained; new output
is saved separately. PowerShell parser checks on both changed scripts, Ruff on the
new Python test, isolated Python compilation, and Git diff whitespace validation
PASS. The full canonical Python suite was not rerun for this small scoped repair;
earlier canonical results are historical evidence, not new validation.

## Preservation and evidence

Evidence: `logs/diagnostics/r7e44d-20261016/`, including before-source copies,
minimal source diffs, test log, reproducer output, protected-file hash baseline,
verification JSON, and the roadmap before-copy. Exact deltas against the before
copies contain only the compatibility conversions and their comments. Existing
unrelated manager changes and all prior repository work remain present.

Root/backend environment files, PAPER journal, and frozen challenger membership
are byte-identical to the beginning of R7E44D. The owner, runtime manifest, stop
request and lifecycle locks remain absent. This is a filesystem preservation check,
not a new live runtime acceptance claim. No manager Status/recovery/start/stop,
process signals, Docker actions, Genesis access, shortcut changes, staging, commits,
or pushes were performed. No runtime manifest was fabricated.

## Next execution — separate R7E44E approval required

Recommend one controlled Gaming Mode runtime acceptance retry after explicit approval:
fresh branch/worktree/evidence and conclusive process/ownership preflight; abort if
ambiguous; supported Gaming Mode launcher; actual API PID/run/environment verification;
API/dashboard readiness; effective gaming discovery cadence and independent normal
8-second PAPER management; PAPER_ONLY/MANUAL_ONLY and risk/reconciliation checks;
basic CPU/RAM samples; one owned graceful shutdown and final orphan/record checks.
The fixture result supports that retry but cannot replace actual runtime acceptance.
R7E45 extended benchmarking and R7E46 optimization remain unapproved.

The full canonical roadmap retains the permanent gaming objective, strict Atlas /
Genesis separation, all open evidence/activation/release gates, and the complete
Prediction Market Intelligence V2 phase. R7E44D authorizes no further runtime action.
