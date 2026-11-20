# Forecast import ambiguity continuation — 2026-10-21

Confirmed defect: an existing actual V2 companion source report accepted a conflicting duplicate production_approved key after a valid outer byte digest was recomputed. Original executable reproduction retained in logs/diagnostics/forecast-strict-json-20261021/pre-fix-reproduction.txt.

Minimal correction: forecast parse retains native JSON syntax validation then uses the same bounded token/key-set refusal contract as the market consumer before safety traversal or scoring. Refuses outer/inner/nested decoded duplicate keys, including identical values and Unicode spelling aliases. Does not change forecast values, scoring, canonical model pairing, denominators or immutable source packets. Valid escaped report strings, sibling keys and pretty envelopes remain compatible. Source README records the contract.

Nine focused cases cover conflicting/identical/escaped safety keys, nested outcomes, duplicate outer digest, V2 source report, unchanged real V2 results, formatting and loader clearing. Full offline JavaScript540 passed, zero failed/skipped. Two end-to-end Python package/extract tests passed in1.56s. Targeted ESLint and diff integrity passed. Prior531/520 and56/604/655 results retained separately, not summed or claimed rerun. No backend/PowerShell source changes.

Fresh workspace built and explicit pinned verification passed: D:\Work\Project Atlas\logs\diagnostics\forecast-strict-json-20261021\workspace; manifestSHA256 fb02b88f3e5613633d955aa722748a604d8eb96892d3cdfb8a1d74d9e11871cf. Old artifacts unchanged. Native browser acceptance remains NOT_ESTABLISHED after earlier file-URL policy rejection; no workaround attempted. Node VM/DOM and byte tests are not native-browser visual/security proof.

All21 release decisions and startup lock unchanged. Production NO-GO; officialAFI1–10 PENDING. No production/provider/Atlas/Docker/Genesis, protected storage/config/ACL/shortcut/volume, trading/Discord or Git mutations. No runtime-health inference.

Next: verify market and forecast strict-key lexical contracts with adversarial escaped-backslash/Unicode/bracket-string corpora and differential valid-input tests, then select the next integrated offline forecast/outcome-accountability functionality from the permanent directive rather than extending audits. Existing Python dataset _json already uses object_pairs_hook; do not duplicate that infrastructure. Preserve every phase and external rights, operational lifecycle/backup/restore, Gaming, cash scope, lint, consent and Prediction V2 gates.
