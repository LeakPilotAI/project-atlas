# Atlas V4 unselected code installation ? offline preparation (2026-11-08)

**Status:** PROPOSAL NOT PERMISSION. No new installed/selected release, no financial PAPER Start/Stop, no providers or desktop shortcut rewiring. Canonical acceptance: **0/9 gates formally closed**.

## Exact reviewed source candidate

- Proposed release commit: `fc07ba532f9b88a2b6d281a4f5c60ef2b72deaed`.
- Source-only archive: `logs/diagnostics/final-launch-commissioning-20261108/offline-candidate-fc07ba532f9b/atlas-source.zip`.
- Archive SHA-256: `3f366b14f85d6dfce990ff98ca2b573176e1a838b3054b957894b04a060f2855`.
- Previously independently verified source inventory: 916 pinned files; native installation copy plan: 10,482 files including approved dependency inventory.
- The native release destination `D:\AtlasRuntime\releases\fc07ba532f9b88a2b6d281a4f5c60ef2b72deaed` and exact diagnostic receipt path were both absent at offline preflight. This is a **create-only** path; if either exists at execution time, refuse, preserve it, and independently reconcile rather than retry/overwrite.

## Explicitly unapproved installation proposal

- `docs/QD_UNSELECTED_CODE_INSTALL_PROPOSAL_V4_2026-11-08.json`; proposal SHA-256 `43623d87993478fa89fb0ebfac5be3e2bd761f9cfe1185bab5139d17d0305869`.
- The V4 proposal binds source archive SHA, source inventory digest, dependency receipt digest, target, diagnostic receipt, and hashes for the three local installer adapter modules.
- `scripts/install_verified_release.py` was extended to permit **only this exact additional V4 proposal path** via its existing hash-pinned and separately approved execution flow, using the current Cloudflare/Google Windows time-source roster. Prior V2/V3 proposal recognition and all mandatory approval gates remain unchanged.
- This updated installer is a **workspace-side deployment tool**, not a change to the prebuilt `fc07ba` runtime payload. Do not rebuild the entire runtime archive solely to include a proposal or installer entry whitelist; any additional runtime-source change would require a new reviewed archive. No automatic installation, selector mutation, authority grant, financial account inception or provider checks.

## Verified offline checks

- Native installer proposal/schema, source archive and exact dependency copy plan validated with no code copy.
- Static PAPER release policy audit: 802 source files, zero violations reported.
- Focused offline new V4 proposal and native installation test suites: **99 passed, 0 failed**. Broader prior PAPER/desktop regression was **465 passed, 1 skipped, 0 failed** before the installer whitelist-only change.
- Targeted new formatting/unused-variable checks passed. Defensive broad-exception lint warnings remain for separate review; no safety control was weakened to silence them.

## Remaining boundaries

- Real release installation and source selection require **separate explicit operator authorizations**, not this proposal. Installation itself must not activate financial PAPER Start, mutate existing selected release, or contact providers.
- Native two-account inception and enrollment, source/provider rights and supervised PAPER activation remain outstanding; real Start/Stop/flatten/restart/browser/listener/soak checks remain deferred to the grouped FINAL LAUNCH CERTIFICATION.
