# Atlas V4 existing-epoch structural review — 2026-11-08

**Decision-ready technical finding:** the existing empty Quality Dips and Hyperliquid personal PAPER epoch directories are structurally compatible with the current V4-bound **source-only proposal**. Creating additional directories just to rename the Hyperliquid release-labeled path is not technically required by the reviewed enrollment schemas. **Reuse is NOT operationally accepted or authorized by this finding.** Canonical nine-gate acceptance remains **0/9**.

## Native facts verified without mutation

- Selected V4 release: `fc07ba532f9b88a2b6d281a4f5c60ef2b72deaed`, release artifact digest `d7724787ef6f459d3a130f915dc7823ccc3de9c3d8337af4b948879e211ee5b5`, immutable native selector revision **9**. A fresh `NativeInstalledReleaseVerifier.open` passed for the genuinely installed V4 candidate.
- Exact V4 native support package was independently checked through `support_deployment.verify_deployment` with receipt SHA-256 `98fc722a5f0fd9034dc7559ed508afb427a6a93a93ae363fcae0cf5329c68bef`; its installation had zero financial actions.
- V4 source-only draft `docs/ATLAS_TWO_ACCOUNT_V4_UNAPPROVED_ENROLLMENT_BUNDLE_2026-11-08.json` was verified against SHA-256 `fd40c907ee6f62a1eabff4d347c1ca17c4438c8ddd3e226bc92d69db8290fbd1`; both financial manifests retain separate simulated USD 1,000 / USDC 1,000 opening amounts and exact V4 artifact/digest bindings.
- Each **Quality Dips** existing root (`qd-paper-20261024-b2cbd50cfe59475fa3726549365cc253`) and each **Hyperliquid** existing root (`hl-paper-20261108-de437abe-v1`) passed genuine Windows native identity/ACL verification; all **12 of 12** roles were distinct and empty. No source, report, projection, control, coordination or custody file was created. `D:\AtlasCustody\PersonalPaper` had zero activation entries.
- The Hyperliquid epoch's historical `de437abe` component is a directory label, **not proof that old release code or its financial state was adopted**. The reviewed pure `validate_enrollment`, `validate_manifest` and `validate_personal_inception` requirements bind exact release digest, manifest digest, epoch string, resource paths and native IDs; they do not infer acceptance from folder name or empty directories. V4's *full* native account validators still refuse absent writer identities and acceptance ID.
- Host-only independent factual audit was saved **create-only** at `logs/diagnostics/atlas-v4-epoch-structural-compatibility-r9-20261108.json`, SHA-256 `a06eaa8b1410c4917dc14b6af9cf82eb12318d1c46737c89bd05b7434dc217ef`. The audit explicitly records operator adoption, financial inception, provider authorization and PAPER startup as **false**. It is ignored by Git; no existing account evidence was overwritten.

## Scoped recommendation, not adoption

**Avoid creating another six-root epoch for either account merely to change its directory name.** Keep the twelve existing empty, separately pinned native root identities as the preferred candidate, conditional on explicit accepted initial-epoch choice and genuine proof that no historical financial obligation is being adopted. If independent commissioning later discovers an existing financial owner, a nonempty native root, a conflicting epoch or incompatible accepted release/rights, **refuse and plan a separate new epoch**; never reset, delete, rename, retrofit, or re-incept the old root.

This resolves the **technical folder-name compatibility question**, not the B1 account-epoch authority or historical exclusion gate. No source-only review may publish initial balances or pretend a past provisional `opened_at` is real inception time. Personal policy disallows legacy adoption and assuming old positions are closed.

## Guarded follow-up and tests

- New tests assert that V4 proposal epoch strings and all exact original native paths stay unchanged rather than silently migrating them, while unaccepted financial inception and enrollment flags remain false.
- Scoped offline unit tests: **80 passed, 10 skipped, zero failed**, including V4 draft, personal inception and QD enrollment. Skips are not operational acceptance.
- **Next genuine dependency:** confirm the candidate empty epochs under the sole-operator initial account scope, then at final launch obtain **actual process PID/creation FILETIME and owner leases, native acceptance IDs, real inception clock, financial writer/custody record, and E1 accepted provider fees/funding/market-source rights** before any once-only simulated cash publication. Both accounts must receive independent verified inception/readback and no startup without final session authorization.
- Actual PAPER Start/Stop/flatten, browser/listener, restart and sustained soak remain deferred to final launch certification, and the no-provider-check hold remains active. No real orders, Project Genesis modification, desktop shortcut rewiring or Windows boot startup.
