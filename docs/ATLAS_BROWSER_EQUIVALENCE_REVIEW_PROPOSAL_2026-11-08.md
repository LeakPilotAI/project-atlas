# Atlas browser acceptance: proposed equivalent-contract review (2026-11-08)

Status: PROPOSAL ONLY. NOT APPROVED. NO GATE CHANGE. PAPER PRODUCTION NO-GO.

## Existing constraint
The November 7 commissioning report requires a trusted Windows Chrome tab provider, verified tab identity/current URL/post-navigation origin, and independent active-listener agreement. A terminal-driven Chrome run, HTTP 200, DOM dump, screenshot, or generic browser tool is not automatically equivalent. The October 26 headless Chrome acceptance was synthetic and cannot be promoted to operational acceptance.

## Proposed review path
1. Identify the original signed/approved browser witness contract and the exact origin/identity evidence it requires. Retain it unchanged as the baseline.
2. Evaluate whether an operator-owned local Chrome DevTools Protocol session, launched with an isolated temporary profile and explicit loopback endpoint, can provide independent tab identity, navigation, current origin and final rendered dashboard state. Treat CDP as an untrusted candidate until independently reviewed. Do not attach to an existing personal Chrome profile or enable remote debugging on the normal profile.
3. Collect browser witness, native listener, CIM/IP Helper and netstat observations independently, preserving their raw disagreements. Do not infer listener agreement from HTTP success or SO_ACCEPTCONN alone.
4. Confirm browser witness binds to the exact installed application, release, owned child PID, loopback origin, and bounded session, and that graceful Stop releases owned resources with no unrelated process termination.
5. Require explicit review and acceptance of any equivalent contract before using it for an operational gate. Until then, run only isolated disposable diagnostics and label them NONFINANCIAL / NOT ACCEPTED.

## Fail-closed criteria
Missing provider identity, missing independent listener evidence, disagreement between readers, stale browser origin, unexpected profile, missing owned-child binding, or incomplete Stop witness => REJECT. No relaxation of existing acceptance predicates. No financial enrollment, startup, source publication or account inception is authorized by this proposal.

## Other independent blockers
Native Quality Dips and Hyperliquid enrollment, accepted provider rights and current market evidence, source publication, financial Start/Stop flatten/reconciliation and multi-day supervised PAPER soak remain separate gates. Browser acceptance alone cannot authorize full PAPER production.

## Operator burden
No additional Chrome installation or user setup should be requested before this candidate is reviewed against the original contract. The existing VS Code Desktop Commander terminal connection is not a trusted Chrome tab provider.

## 2026-11-08 native disposable listener recheck (not accepted)
Executed opt-in `tests/test_acceptance_socket_native_disposable.py` on Windows using an ephemeral owned loopback child (no installed Atlas host and no financial operations). The test FAILED at the `listening` collection: the resource audit exited 2 with `APP_PROCESS_NOT_RELEASED`; CIM returned a scoped TCP row for the disposable port with `state: 0` rather than an independently accepted LISTENING observation. This does not establish three-reader agreement. Do not promote browser CDP preview success into Gate 1 acceptance. The current native resource audit/reader disagreement requires diagnosis under unchanged validators before retrying genuine installed-host browser commissioning.
