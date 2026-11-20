# Synthetic daily-chart to AFI bridge

`daily_afi_bridge.py` is a pure, explicit-input adapter. It starts no provider,
collector, database, scanner, trading service or background task. No default path,
credentials, production route or real-data permission is supplied.

`normalize_daily_chart` accepts bounded Yahoo-chart-shaped **synthetic** bytes,
explicit symbol/class, receipt clock and these declared conventions:

- `fixture_mode='SYNTHETIC_REPLAY'`
- `price_policy='UNADJUSTED'`
- `session_scope='REGULAR_ONLY'`

Only USD U.S. equity/ETF daily series indexed at the exact regular opening are
supported. Daily close event time is the existing calendar's actual close, including
DST and early closes; it is never midnight or opening time. The calendar remains
bounded to2026–2028 and does not prove unscheduled exchange closures. Unknown or
contradictory instrument/timezone/scope, incomplete bars, null/unsafe OHLCV, minute
series and nonempty corporate-action metadata refuse. Adjusted-close columns are
not consumed. This is a declared fixture subset, not verified live vendor semantics.

`build_daily_dataset` accepts a bounded ordered list of dictionaries containing
`payload_bytes`, exact `sha256` and `received_at`. The caller must also supply the
point-in-time `universe` row with listing/availability/delisting fields, dataset ID,
version, cutoff and the conventions above. Never infer listing date from first bar.
It returns `DailyDataset(manifest_bytes, payload_bytes, audit_bytes, review)` using
the existing AFI dataset contracts. `US_ETF` maps explicitly to AFI `ETF`.

All availability times are caller-recorded receipts, **not authenticated vendor
publication times**. A late historical download never becomes evidence known before
that receipt. Unchanged confirmations preserve the first receipt within the supplied
archive; value changes/reverts append receipt-bound revisions. Identical retries do
not multiply observations. The audit binds every unique supplied receipt/snapshot,
not independently complete history. Retain originals across dataset versions: a
latest-only replacement of committed records is refused by existing outcome checks.

Known gaps/short history remain `INSUFFICIENT_EVIDENCE`, with no imputation. An
`ACCEPTED_SYNTHETIC` review is byte/contract acceptance, not provider rights, source
truth, universe completeness, corporate-action reconciliation, live freshness,
calibration or production authority. Existing baseline freshness/known-at checks
still apply. Nonzero reported delay does not establish its unit or live status.

No persistence acknowledgement is returned by these pure functions. Use the
existing checked `publish_research_text` only in an explicit authorized isolated
root; returned JSON is capped at its2MB publication bound. Multi-file publication
is not an atomic transaction or hardware power-loss guarantee. Preserve partial
failures and never clear protected recovery state. No PAPER order is involved.

Captured end-to-end stock/ETF examples and exact continuation are recorded in
`docs/DAILY_AFI_BRIDGE_CONTINUATION_2026-10-21.md` and the corresponding diagnostics.
Real provider entitlements, permissions, wire conventions and budgets remain
separate blocked acceptance gates. Production remains NO-GO.
