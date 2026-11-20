# Candidate verifier continuation — October 20, 2026

## New working functionality

scripts/build_release_candidate.py now exposes verify_candidate(archive, expected_sha256=...) as a read-only library operation in the existing packaging module. It requires an explicit lowercase retained SHA256, reads a regular singly linked archive through verified source handles, and checks complete manifest declarations/member hashes/lengths. It refuses duplicate JSON keys/declarations/ZIP members, undeclared/missing members, unsafe paths, non-regular ZIP metadata, unsupported compression/encryption and activating manifest claims. It reads the bounded observed-dependency companion to validate its CRC. No extraction, install, execution, import, deployment or activation occurs.

Explicit bounds:64MiB compressed input,128MiB declared decoded total,16MiB per entry,1MiB manifest,5000 members. Tests mutate only tiny synthetic central-directory size declarations to establish refusal before decompression; they do not allocate a real decompression bomb. Source-reader maximum_bytes limits its content read too. Limits are resource safeguards, not a hard CPU/wall-time guarantee, denial-of-service certification or privileged-writer exclusion.

Returned supplied_bytes_consistent=true never implies source_authenticated, installation_verified or activation_approved; all remain false. A retained digest must be supplied separately. Rehashing an attacker-created unsigned candidate cannot create authority. Observed installed requirements remain an inventory, not a dependency lock or redistribution license proof. No whole current working-tree release archive or production data was created/read for this acceptance.

## Exact validation

24 focused verifier tests pass, including a no-filesystem-change positive control, invalid/mismatched pins, altered hashes/lengths, malformed manifests, source/membership and size/count controls. Combined native suite:51 passed in19.71s, zero failures/skips (24 verifier +9 identity +8 packaging +10 extracted equity/ETF market cases). Nested extracted23 Node cases are not double-counted against prior362 JavaScript cases. Existing604 AFI and362 JavaScript acceptance logs/hashes verified and preserved; no redundant broad rerun. Targeted Ruff and Python compilation pass; Git diff check passes. Existing PowerShell updater parser acceptance retained with unchanged updater hash.

Original/intermediate source-identity errors and10 extracted-market sandbox timeouts remain immutable evidence in preceding diagnostics directories; native compatibility/market corrections and acceptance are documented in SOURCE_IDENTITY_CONTINUATION and EXTRACTED_MARKET_CONTINUATION. Three inherited frontend builder require-import findings remain unchanged, with no lint waiver.

## Market readiness / remaining blockers

Offline forecast viewer build plus extracted market research paths are technically verified with deterministic fixtures and installed host dependencies. Equity/ETF premarket, regular, after-hours, DST and early-close cases cover both bar and quote-reference persistence/API/browser parsing. No native visual review, clean-machine installation, real feed or full Atlas startup acceptance is implied. No fresh runtime census performed.

Actual live-data session: NO-GO until provider-specific authorized automated-use/session/history/storage/display permissions, entitlements/credentials, wire request budgets and timestamp/delay/adjustment semantics are validated under explicit authorization, and a fixed observation-only release passes protected admission/lifecycle acceptance. No provider credentials, subscriptions or entitlement are assumed present or absent. Shortest safe path remains one provider with documented scope → approved bounded observation-only runtime acceptance → fresh real timestamps/budget verification → read-only dashboard. PAPER/live/Discord gates remain closed.

All21 decisions unchanged (5 scoped PASS/13 BLOCKED/3 NOT_TESTED); production NO-GO. Seven phases, AFI1–10 PENDING, Gaming objective, Genesis separation, E136 consent/no-backfill and Prediction Market Intelligence V2 safeguards remain intact. No service/provider/Atlas/Docker/Genesis operation, protected configuration/state/ACL/shortcut/volume, real backup/restore or Git staging/commit/push/reset/cleanup.

## Exact continuation at forced context boundary

Latest verified evidence: logs/diagnostics/candidate-verifier-20261020/result.json and intended-file-hashes.json (135 paths). The approved updater verifies backup equality, exact managed read-back and byte-identical history outside the managed block. Canonical21-gate hash and startup-lock hash remain unchanged. Goal preserved; last read-only status usageLimited from prior limit. No duplicate Goal, status reset, scheduler, daemon or automation. Goal/roadmap are not complete; resume the user-authorized offline loop.

Next automatically selected task: expose the existing read-only verifier via a backwards-compatible explicit CLI mode requiring --verify and --expected-sha256, preserving the original positional build-destination interface. Test exclusive mode selection, missing/invalid pin, refusal exit codes, stable JSON status and no extraction/activation. Use new disposable diagnostics paths; no full working-tree archive unless its inputs are independently reviewed. Afterward select the next useful offline roadmap task without waiting for milestone approval. Do not repeat604/362 completed suites without a change-specific reason. Preserve every existing file/pin and current 21 decisions, and checkpoint with the existing updater at the next forced boundary.
