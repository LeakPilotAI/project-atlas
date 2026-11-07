# Immutable synthetic chart source archive — October 20, 2026

Scoped offline acceptance; production NO-GO; existing Goal active/incomplete. Previous goal turn classified PROGRESS: implemented three tested market-data increments and verified checkpoint. This turn advances retained source reproducibility.

## Working functionality

scripts/observation_runtime/chart_archive.py adds a callable exporter/verifier and explicit offline CLI. An ATLAS_CHART_ARCHIVE_REQUEST_V1 supplies a portable source filename, exact caller SHA-256, observation clock and asset class. Existing BundleReader prevents path escapes and symlink/junction paths; archive inputs additionally reject hard links. Source bytes, including original trailing CRLF/whitespace, are retained under their content hash. A narrow reviewed synthetic schema rejects unrequested fields before any publication, rather than copying arbitrary response metadata, credentials or private fields. Only chart/result/meta/timestamp/OHLCV and the explicitly reviewed optional type/timezone/delay/adjusted-close fields are eligible.

Existing chart validation and diagnostic run before writes. Existing immutable publisher retains original source, JSON report, scriptless readable HTML and provenance sidecar; a canonical receipt is published last. No ARCHIVED acknowledgement occurs until all five exact files re-read and the verifier reconstructs every derived byte from the retained original using the exact observation clock. Copying all five files to another explicit root is sufficient for portable verification; original request directory is not required. Caller retains the receipt SHA-256 independently of verification input selection. A hash is consistency evidence, not provider authenticity, licensing or an independent rollback witness.

Exact retries preserve previous bytes. Missing/changed companions, altered receipt pins, rehashed contradictory reports, hard links, unknown source fields and ambiguous paths refuse. Disk/full/publication or verification failures preserve partial files and do not acknowledge completion. A partial receipt collision cannot be silently repaired or overwritten on retry. This is not a multi-file transaction, power-loss certification, backup, independent custody or protection against privileged/concurrent namespace attacks. Before/after path checks are not a kernel-backed identity/exclusion guarantee.

The CLI supports --bundle-root with either --request/--output-root or --verify-receipt/--expected-receipt-sha256. It has no default source/destination, provider, service, credentials, recovery or startup hooks. Refusal uses a constant error rather than dumping input or filesystem details. Use only explicit disposable/offline fixtures; these commands do not authorize real data collection.

## Evidence

26 new archive tests pass. Final broader isolated selection494 Python passed,0 failed/skipped,19.09s; includes prior468 market/quality/replay/source/budget/deadline/shutdown/PAPER cases. Existing Node suites271 passed from prior retained run; frontend unchanged. Targeted Ruff and compilation pass, approved-updater PowerShell parsing and Git diff integrity recorded. No full canonical suite or complete lint waiver claimed.

First focused run21 passed/1 failed because restricted Windows denied creation of the disposable hard link. Native execution with narrowly authorized fixture filesystem access passed all22 cases; four later integration/failure cases bring final26. Both original failure and successful native evidence retained. A narrow import ordering lint finding was corrected, no application behavior waiver.

Actual retained original -> strict normalization -> disposable SQLite -> in-process ASGI JSON/HTML -> existing Node dashboard consumer passes. Synthetic price101 is a fixture assertion, not a market observation. Original input files and copied portable bundle are byte-verified. Partial source/receipt failures, complete receipt verification interruption and missing/tampered companions never become success.

## Readiness and gates

Inert offline market factory/consumer/exporter are technically usable for synthetic research. Complete Atlas/dashboard startup remains locked and NOT authorized, without fresh runtime/Docker census or real server health acceptance. Premarket/regular/after-hours, early-close and DST fixture paths remain tested; live session support unverified. No provider entitlement/API key/subscription is assumed present or absent.

Live prerequisites unchanged: establish provider/exchange automated-use, equity/ETF session coverage, real-time/delay and historical/storage/display/redistribution rights; safely validate credentials; accept actual HTTP internal-hop budgets/deadlines and vendor timestamps/adjustment semantics; separately approve observation-only fixed runtime/admission integration and bounded startup/data/shutdown acceptance. Repaired launcher is not this profile. No provider traffic or production integration performed.

Canonical21 decisions remain byte-identical:5 scoped PASS,13 BLOCKED,3 NOT_TESTED. Startup lock unchanged; production NO-GO. No Atlas/Docker/Genesis activity, real volumes/backups/restores, trading/PAPER/prediction/Discord, protected config/ACL/shortcut or Git mutation. Gaming objective and normal PAPER cadence preserved.

## Next automatic execution

Add usable offline frontend acceptance of these retained chart diagnostics without starting Atlas. Reuse existing local-file/cryptographic validation patterns; accept explicitly supplied five-file archive bytes with an exact caller-retained receipt pin, verify bounded content identities and strict denied-authority/schema contracts, then display raw-versus-reported-adjusted prices and unknown delay/basis clearly. Browser byte verification must be labeled BYTE_INTEGRITY_ONLY, not Python source reproduction, provider authentication, live freshness or admission. No fetch/network, filesystem discovery, execution, source-content dump or production page integration. Test missing/changed/late loads, stale display clearing, mismatched pins and actual Python-generated archive. First inspect existing frontend contracts/AGENTS/docs to avoid duplication. Continue independent seven-phase work afterward.

Seven phases preserved in master:1 core lifecycle/provider/cash/lint/package/backup/restoration/Gaming;2 Evidence Engine PIT/immutable history/replay/calibration/costs/leakage;3 bounded crypto PAPER rules/depth/costs/settlement, no activation;4 cross-market intelligence;5 SaaS/demand/auth/tenant/rights/billing;6 institutional security/governance/compliance;7 commercial evidence. AFI-1–10 PENDING; E136 consent/recovery/no-backfill, prediction exactly-once/predeadline/autoflat and PM-V2 no combos/stacking/averaging/opposing YES+NO remain. PAPER_ONLY/MANUAL_ONLY; no VPS/external schedulers. Full authoritative phase text and21 identities remain in managed checkpoint.
