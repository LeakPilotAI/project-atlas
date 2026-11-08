# Atlas V4 revision-9 support bundle: offline source proposal (2026-11-08)

**Status: PACKAGE PREPARED + OFFLINE VERIFIED, NOT INSTALLED OR EXECUTION AUTHORITY.** Current selected application is V4 `fc07ba532f9b88a2b6d281a4f5c60ef2b72deaed`, native selector revision 9. This document does not authorize support installation, an account inception, a provider call, a PAPER Start, desktop rewiring, or live orders. Canonical accepted operational gates remain **0/9**.

## Scope of exact new support bundle
- Source-only builder: existing `scripts.build_support_deployment.build` with explicit V2 recovery-style manifest and previous installed support child `2bd578c209d2cc046bd9de7cf4cc51049081f6649ea48e660efcf94d9ca34f1d` as immutable historical input.
- Offline private package location: `logs/diagnostics/atlas-v4-support-offline-proposal-20261108-r9/` containing `deployment.json` and `support-source.zip`; not part of Git and not in the operational destination.
- Proposed deployment manifest schema: `QD_SUPPORT_DEPLOYMENT_V2`; manifest SHA-256: `551b8110f6d18f8c1466e0762c791d841717f2b73edff96280559fccbd76b6d0`.
- Proposed archive SHA-256: `e704fea0088bfceeca4fdee88eda19b8dc57eca434297aca164b6e697d1398ab`.
- Exact support package digest: `74bc6dc9a9959f88af3378dbcf371b8014e3969c6152b4beb9112ad36cc3a8c8`.
- Proposed create-only launcher path: `D:\AtlasRuntime\launchers\74bc6dc9a9959f88af3378dbcf371b8014e3969c6152b4beb9112ad36cc3a8c8`. Corresponding control sibling is `D:\AtlasRuntime\support-installations\74bc6dc9a9959f88af3378dbcf371b8014e3969c6152b4beb9112ad36cc3a8c8`. Both were absent at offline preparation. **Do not overwrite or adopt either if later present.**
- Archive has 10 individually hashed source/support files and 3 directory entries; verified by existing `support_deployment.prepare` exact manifest/namespace/hash checks and negative authority flags.
- Application receipt SHA-256: `2b282dc6ee1dc84e9742f672b972e7ebd5809ba3fda073e7073be5f25d7eadd7`; installed artifact digest: `d7724787ef6f459d3a130f915dc7823ccc3de9c3d8337af4b948879e211ee5b5`.

## Actual host and regression evidence
- Verified all three preexisting native parent root identities using separate actual `WindowsOutput` handle opens, matching independently retained native support receipt: launcher parent `[4004218753,327680,1532783]`; support-installations parent `[4004218753,327680,1532784]`; selector parent `[4004218753,65536,1532785]`. No parent or account root was created, repaired, or changed.
- Offline test run initially produced **16 pass, 51 setup errors** because pytest default `tmp_path` used Windows `C:\Users\...\Temp`, contrary to the support builder's exact `D:\Work\Project Atlas\logs\diagnostics` boundary. This is a test-harness/temp-root mismatch, not a demonstrated V4 archive failure. After rerunning the **same** two suites with `--basetemp` inside the approved diagnostics root, **67 passed, zero failed/errors**. No production path/ACL/source restriction was relaxed.
- The package is **source-only**. It does not validate a real installed support readback, operational browser/listener, PAPER account, provider entitlement, Stop or financial launch. Previously installed nonfinancial support children remain pinned to older releases.

## Next dependency and required decision
1. Obtain **distinct exact authorization** for the new nonfinancial V4 support create-only installation after fresh native source/parent/release/time checks; use the exact pinned manifest and archive. On any mismatch or partial destination, refuse and preserve evidence, never retry into an existing target.
2. Perform independent native installed support readback and selector consistency. Selection is already V4/r9; **do not reselect or reset**.
3. Reconcile/review QD and HL enrollment drafts currently pinned to the older r8 application digest; do not silently repin existing financial namespaces. Confirm exact account epoch, authorizations, provider rights, owner/writer identities and once-only inception evidence before financial state.
4. Group actual PAPER Start/Stop/flatten/reopen/listener/browser/end-to-end/soak acceptance at FINAL LAUNCH, under separate explicit authority. Continue with no Genesis changes, no automatic Windows startup, no live orders.

**Development progress context:** local Git log reported 184 commits since 2026-11-07 21:00 CST before this checkpoint; counts describe source activity, not certified operating completion. Formal operational acceptance remains 0/9.
