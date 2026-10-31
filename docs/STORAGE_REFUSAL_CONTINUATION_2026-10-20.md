# Continued offline risk-state and PAPER-book refusal corrections

Production NO-GO. No trading authority, risk limit, cash-scanner scope, protected
state, startup path, production data or 21-gate decision changed. No services,
providers, Docker, Genesis, trading or Discord were activated. Work follows the
market replay and immutable forecast-continuation implementation documented in
`MARKET_DATA_REPLAY_CONTINUATION_2026-10-20.md`.

## Confirmed defects and minimal changes

`paper_risk_controls.py` accepted malformed saved session_net_r, silently replaced
some values with0 and still marked controls reliable. Boolean/nonfinite values
could also reach apparently reliable state. Seven original-source fault cases
reproduce this. Loading now requires explicit Boolean kill-switch and finite,
non-Boolean loss evidence. Malformed/missing fields mark controls unreliable;
existing downstream risk checks refuse new exposure. The risk thresholds and
PAPER policy are unchanged. Numeric legacy string evidence remains supported.

Saving previously used an unchecked buffered temporary write without flush/fsync.
It now uses the existing strict write_flushed helper, exclusive unique temporary
file, atomic replace and platform-scoped sync_parent. Failure or interruption marks
the instance unreliable, preserves original exception and temporary evidence, and
refuses subsequent save/load attempts on that instance. A failure after replacement
is uncertain, never successful. Corrupt loaded state cannot be silently overwritten.
Snapshot schema and saved JSON field names are unchanged. No repair/reset operation
is introduced. The in-memory failure latch is not a cross-process/restart fence,
independent recovery authority or proof of namespace persistence on Windows.

`investment/paper_book.py` returned a new empty book on existing-file read/decode
failure. It now raises PaperBookStateUnavailable with original context. Missing-file
legacy initialization remains unchanged; no file is created by load. Five original
read/decode faults reproduce the defect, and all six corrected load cases pass.
This narrowly changes the exception path, not ledger/snapshot formats, fill
execution, allocation, accounting, prices or scope. Broader PaperBook save/ledger
atomicity, replay/duplicates, valid-but-semantic corruption and crash reconciliation
remain separate work. A returned book is not a certification of storage integrity.

## Exact evidence

Diagnostics: `logs/diagnostics/market-readiness-20261020`.

- Final combined storage/risk/durable/shutdown/investment suite:143 passed,0 failed/
  skipped,7.49s.11 new risk cases and6 new book cases; earlier84/59 runs are subsets,
  not extra independent tests.
- Original risk source:7 failures,4 deselected. Original book source:5 failures,
  1 deselected using RuntimeError compatibility solely in the baseline reproducer.
  First baseline attempt failed collection because the new exception class was
  absent from original source; that harness evidence is preserved separately.
- Risk source/new tests targeted Ruff pass. PaperBook whole-file inherited lint
  debt remains recorded in book-ruff-before.json/book-ruff-after.json; no broad
  cleanup or policy waiver. New test file passes Ruff.
- Earlier independent increments:95 market/provider tests,552 full AFI tests,
  144 JavaScript tests passed. No entire-application-suite claim. Static compilation,
  selected PowerShell parsing and whitespace checks are recorded separately.

No real power loss, filesystem crash, backup/restore, live provider, native browser
or operational shutdown was tested. No fsync claim extends to all hardware failure.
Main Atlas dashboard startup and real equity/ETF collection remain BLOCKED; the
separate replay dashboard factory works in-process using deterministic fixtures.
Provider automated-use/display/storage rights, actual feed/session/delay coverage,
aggregate HTTP budgets and operator-authorized isolated runtime acceptance remain
necessary. Existing production startup lock is intact.

## Exact continuation

Primary priority remains market-data usability. The offline dashboard response
consumer now accepts actual API exports and refuses schema/mode/authority, temporal,
price-kind and coverage contradictions; failed imports clear old display.13 new
consumer cases and targeted ESLint pass. No production mount or network fetch.
Next resume PaperBook snapshot/ledger acknowledgement adjudication, with original fault
reproducers before any change and explicit multi-file/restart limitations. Do not
duplicate already implemented pending-limit/prediction persistence corrections.

All seven phases and21 gate decisions remain in the verified permanent checkpoint.
All AFI milestones remain PENDING despite scoped functionality. The complete
roadmap is not finished. Preserve the existing native Goal; last tool observation
was BLOCKED, and no duplicate or external continuation mechanism was created.
