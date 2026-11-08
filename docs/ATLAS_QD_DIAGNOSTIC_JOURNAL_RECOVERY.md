# Atlas Quality Dips diagnostic journal recovery

Scope: **read-only research diagnostics only**. This is not financial custody, a trading ledger, or permission to start PAPER/live trading. Never modify the damaged original.

## Safe operator procedure

1. Stop the diagnostic acquisition process; do not use these commands against an actively written journal. Preserve the original journal and its filesystem metadata.
2. Run `python -m scripts.observation_runtime.qd_free_research_acquisition --inspect-diagnostic-journal PATH_TO_JOURNAL`. Exit 0 means the existing journal is structurally valid; exit 1 refuses invalid or incomplete history.
3. For an interrupted journal, run `python -m scripts.observation_runtime.qd_free_research_acquisition --plan-diagnostic-recovery PATH_TO_JOURNAL`. Only `TRAILING_FRAGMENT_REQUIRES_OPERATOR_REVIEW` with a valid completed prefix is eligible for an explicit export.
4. Run `python -m scripts.observation_runtime.qd_free_research_acquisition --export-diagnostic-recovery PATH_TO_JOURNAL --recovery-output NEW_FILE.jsonl`. The destination must not already exist. **Capture the JSON receipt printed to stdout in a separate file**, e.g. `receipt.json`, without editing the values.
5. Run `python -m scripts.observation_runtime.qd_free_research_acquisition --verify-diagnostic-recovery PATH_TO_JOURNAL --verify-recovery-output NEW_FILE.jsonl --recovery-receipt receipt.json`. A successful result must report `VERIFIED_FOR_OPERATOR_REVIEW` and `resume_authorized: false`.
6. Preserve the damaged original, the recovered export, and the receipt for operator review. Do not automatically replace a journal path or resume acquisition.

## Failure handling and limitations

Any failure or unexpected result is a stop condition. The tooling refuses malformed completed records, absent valid prefixes, tampered sources/exports/receipts, and overwriting an existing export. The recovery receipt contains SHA-256 hashes, which detect changes but **do not prove independent authenticity**. This procedure does not establish historical completeness, provider rights, analyst targets, operational acceptance, PAPER fill authority, desktop lifecycle certification, or live-trading authorization.
