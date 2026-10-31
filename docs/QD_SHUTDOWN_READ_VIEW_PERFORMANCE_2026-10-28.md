# Quality Dips native Stop performance — October 28, 2026

Source base: `e67e7f0e021b3b4db3b0b5999db0ae9e4564f3b1`, branch `chatgpt/atlas-rebuild-v1`. This increment implements a bounded native read optimization and measures complete disposable owned shutdowns. **The eight-second acceptance still fails.** The conditional sole-operator Quality Dips commissioning grant remains unused; no account or provider was activated.

## Implementation and preserved checks

- `scripts/observation_runtime/personal_coordination_store.py`: a mutex-bound, thread-bound immutable read view. Entry and exit validate the complete native evidence cut; nested queries bind the exact root, namespace and observed generation. Writable transactions/publications refuse inside the view. Abandoned ownership refuses without read-side repair or adoption. Original retained handles deny write/delete sharing.
- The same store reuses previously verified immutable prefix decoding. Every original file still passes native identity, protected ACL, link-count, length and binding verification through its retained handle. Newly appended records receive full intent/page/digest/commit/ACK verification. Missing files, foreign tails, rollback or incomplete publication refuse. One latest image and bounded bindings are retained; capacity limits and immutable history are unchanged. This is not a cached financial result or a local anti-rollback authority.
- `backend/app/services/personal_native_coordination.py` exposes the narrow read scope. Existing explicit in-memory test ports keep their original validation behavior.
- `scripts/observation_runtime/personal_financial_authority.py` and `personal_runtime_current.py` use **ownership lease before coordination mutex**, with sealed source/ledger component references. Pre-effect read validation closes before reservation/PENDING or financial publication. Read-only leases may span the coherent cut. Reservation, native financial effect, commit, ACK, audit and UNKNOWN handling are unchanged.
- Existing native pipeline/restart helpers now support an explicitly synthetic parent-observed Stop measurement. New confined workers authenticate their exact process handle/creation identity and self-exit; no process-name/port termination is used. The independent reader can be cold or already ready before Stop, but receives account evidence only after writer exit. Original financial assertions remain unchanged.

New native tests cover nested coherent reads, no writable SQL/native publication in a view, foreign-thread refusal, incomplete tails, ACL-verifier refusal before a value leaves the scope, stale generations, actual handle write/delete denial and genuine competing-process writer exclusion/release. The ACL-change case injects verifier rejection; it is not a claim that every hostile ACL attack was executed.

## Measurements: improvement is real, reliable full acceptance is not

The historical 14.953-second measurement was **12.062 seconds coordinator + 2.891 seconds final readback**, excluding complete owned closure. It remains historical failure evidence.

After coherent-cut and prefix reuse, the final native component profile measured **6.218 seconds coordinator + 0.313 seconds final readback = 6.531 seconds**. Other component profiles in this increment were 8.797, 7.798 and 8.281 seconds. These component measurements are not complete lifecycle acceptance.

The independent parent starts its full timer before sending Stop, verifies synthetic authority/native financial actions, observes actual writer exit, performs independent native read-only restart/reconciliation, verifies unchanged financial hashes and reader exit, and then ends the timer. No timer threshold or financial assertion was relaxed.

| Retained evidence | Reader | Coordinator seconds | Stop through writer exit | Complete Stop, exits and post-exit readback | Eight seconds |
|---|---|---:|---:|---:|---|
| A / sample 1 | Cold | 6.328 | 6.9954842 | 8.6816984 | FAIL |
| A / sample 2 | Cold | 6.140 | 6.7460970 | 8.4984176 | FAIL |
| A / sample 3 | Cold | 6.657 | 7.3099557 | 9.1305104 | FAIL |
| B / sample 1 | Ready before Stop | 7.063 | 7.6744335 | 8.3356081 | FAIL |
| B / sample 2 | Ready before Stop | 8.078 | 8.7517355 | 9.3422630 | FAIL |
| B / sample 3 | Ready before Stop | 7.531 | 8.2687105 | 9.0519594 | FAIL |
| C / sample 1, extra profiling | Ready before Stop | 5.797 | 6.3169587 | 6.8487124 | PASS |

All seven samples passed financial correctness and exact owned-exit/read-only evidence checks: synthetic ending cash **$1,015.9136**, zero remaining quantity and remaining entry costs, no pending projection, matching independently reopened financial state, refused writer rebinding, unchanged financial hashes. **Six timing assertions failed and one passed.** Do not replace these failures with the favourable sample, sum repeated executions as distinct cases, or describe synthetic authorities as actual operational acceptance. These are genuine native/Windows subprocess tests, not a real installed Control Center/browser/operational-clock acceptance.

Detailed C profile: 12 coordination-image publications took 3.8640166 seconds inclusive, including 83 native coordination-file writes taking 3.3463289 seconds. Four financial-file writes took 0.0070639 seconds, three projection-file writes 0.0039621 seconds and one report-file write 0.0013716 seconds. Fourteen native replays took 0.4200106 seconds; three current captures 0.8265992; eight selected reads 0.7092838; three selected verifies 0.2382268; two report publications 0.5110287; two drains 0.0385954. These timings nest and must not be added. Durable coordination-image publication is now the main measured cost. Preserving reservation/PENDING/commit/ACK stages rules out simply deleting writes. Further optimization requires a narrowly reviewed reduction of redundant immutable coordination output, not an increased deadline or weaker verification.

## Validation and retained evidence

- Relevant accounting, current-pin, custody, authority, publisher, risk, clock, report, Stop and restart regression selection: **418 passed, zero failed/skipped**, 17.95 seconds; one existing Starlette/httpx dependency deprecation warning.
- Native read-view safety selection: **8 passed, zero failed/skipped**, 2.16 seconds, including a real separate competing writer process.
- Final focused selection: **90 passed, zero failed/skipped**, 3.49 seconds; overlaps the 418 and is not additional distinct coverage.
- Complete lifecycle timing: **six failed timing assertions, one passed** across seven executions. The last one is a diagnostic, not a replacement acceptance set. Four component-profile executions additionally passed financial correctness and read-only restart assertions.
- Ruff, AST compilation, whitespace checks and PAPER-only static policy audit passed. Static audit scanned 632 runtime source files with zero issues; it grants no startup authority.
- Earlier fixture/mock failures were corrected without relaxing their assertions: explicit in-memory read scope, removal of redundant nested ownership leases, and native-test instrumentation setup. Original failures, all timing attempts and attack evidence remain in local diagnostics.

Private evidence locations are `logs/diagnostics/qd-shutdown-readview-regressions-20261028.txt`, `qd-read-view-native-20261028-e.txt`, `qd-owned-stop-timing-20261028-a/`, `-b/`, `-c/`, their corresponding test outputs, and `qd-shutdown-readview-resource-evidence-20261028.json`. Native component profiles M–P and initial native safety attempts are retained. These files contain disposable identities and are excluded from Git.

The 16 inspected fixture roots total **3,045 entries and 37,917,428 bytes**. Accounting includes seven complete samples, four component roots and five native safety roots, including retained initial failures. No symlink/junction was traversed during the final count. Per-pipeline guards remain 180 seconds, 2,048 entries and 32 MiB; exact workers have self-exit deadlines. All seven measured writer/reader processes and the competing writer exited. No network listener/port was created by these tests. Evidence remains retained; no reset/deletion was performed. These totals exclude diagnostic text and unrelated earlier work.

## Remaining commissioning blockers

1. **Shutdown engineering:** complete samples remain variable (6.8487124–9.3422630 seconds), with six over budget. Required reliable full Stop within eight seconds is unproven. Review coordination write amplification next; preserve complete final ACK/reconciliation and owned exit. Actual installed authority/clock/process composition must still pass after a defensible source improvement.
2. **Clock:** fresh `LocalWindowsClock` acquisition refused with `CLOCK_STATUS_QUERY_FAILED`, service-not-started **0x80070426**. No service start, resync, source/startup change or manual adjustment was performed. No qualifying current uncertainty is asserted. Starting the existing service requires separately scoped permission under this directive, followed by genuine unchanged <=1-second validation.
3. **Current research/execution:** no accepted current Quality Dips source publication/archive, authenticated ranking revision/provenance, provider-rights evidence, instrument/fractional/lot-size/halts/calendar bundle or entitled fresh executable IEX quote has been supplied. Existing adapters and source code are not those inputs. The prior report's provider-rights findings remain; no provider was contacted, subscription activated or stale ranking relabelled as current. A configured IEX key/feed and trading-disabled setting do not prove entitlement or freshness.
4. **Installation and real financial binding:** no new release was installed. Existing release remains `fca29cfe7760a28d2569b8b4b91ed1ea99804c3c`, inventory digest `93e52e897fd2f2f3cc4b17bd3e804e8c598a1a3a8938c2b5c47d386890310c91`. Real activation/resource/session/current-custody binding, once-only $1,000 simulated inception/readback and original dashboard/controls acceptance remain conditional on every mandatory check. No real activation/inception/account balance, provider quote, autonomous pilot or genuine browser result is claimed here.

The minimum sequence remains: resolve and independently measure the full Stop bound; obtain genuine clock and permitted current research/execution evidence; install a newly verified immutable release; validate actual enrollment/custody; perform eligible once-only inception; verify dashboard and controls; execute the authorized total **60-second** QD pilot; reconcile, owned Stop and manual read-only restart. Do not repeat ambiguous publication, extend the pilot or promote partial measurements.

**Read-view source feature: VERIFIED. Overall source completion: NO. New installation: NO. PAPER READY: NO. PILOT COMPLETE: NO. Production: NO-GO.** Sole personal operator authority, original UI, all seven phases and 21 historical decisions, unrelated work, protected accounts and Genesis isolation are preserved. No V5 containment, Hyperliquid inception, real orders or automatic startup was performed.
