# Operational helper identity diagnostic V1 — root cause established

Starting checkpoint **8bc592f07ae7c3409a3a519f47604f3692f59af9**, branch `chatgpt/atlas-rebuild-v1`.

**Confirmed cause: incorrect expected-identity structure introduced by Windows PowerShell 5.1 JSON pipeline handling.** The helper list became one nested array, so the guard compared scalar process identity fields with arrays. Native process identities were stable. No operational state changed, and no deployment was repeated.

## Authorized native session and exact capture

One ordinary-user read-only session ran under the reviewed **60-second / 512-entry / 8-MiB** scope, confined to:

`D:\Work\Project Atlas\logs\diagnostics\qd-helper-ownership-readonly-v1-20261102`

The native session lasted **0.779 seconds**. It reproduced the original orchestration roles: parent, primary interpreter/redirector process and actual worker. Only the reviewed contract fields **PID, native creation FILETIME and full executable image path** were used for ownership. Roles were diagnostic labels, not extra authority. No token identity, credential, nonce, application resource or financial record was collected unnecessarily.

For all **three identities**, native observations taken before and after the PowerShell query matched the original claims exactly. Creation time was also verified through retained native query handles. All three query handles were explicitly closed. Full exact tuples and paths remain private; they are not committed to Git.

| Field | Expected native structure | Actual PowerShell structure from the failed idiom |
|---|---|---|
| Claim collection | Three individual identity objects | **One outer item containing a three-element `System.Object[]`** |
| PID of one identity | One integer | **`System.Object[]` containing all three PIDs** |
| Creation time of one identity | One exact integer FILETIME | **`System.Object[]` containing all three creation times** |
| Executable image of one identity | One full image-path string | **`System.Object[]` containing all three image paths** |

The unchanged parsing idiom was:

```powershell
$claims=@($env:ATLAS_AUTH_HELPER_CLAIMS | ConvertFrom-Json)
```

On the observed Windows PowerShell **5.1.26100.9818**, the JSON array was emitted as a single pipeline object. Wrapping that pipeline in `@(...)` retained a nested array. Member enumeration such as `$identity.created` and `$identity.image` then produced aggregate arrays rather than one helper's scalar values.

In the original operational preflight, candidate lookup used the candidate's scalar PID, but the later `foreach($identity in $claim)` iterated the aggregate array. Its exact creation-time and image comparisons therefore falsely refused. The offline replay using the captured native values reproduced **both** false comparison results for each helper, even though each individual native identity matched.

The new diagnostic exposed the same malformed shape earlier: `GetProcessById($identity.pid)` received an array and reported **“Cannot find an overload for GetProcessById and the argument count: 1.”** Its subsequent harness assertion expected three rows but received one aggregate row, producing a recorded `DIAGNOSTIC_REFUSED` / `AssertionError`. That failure is preserved; the native capture is **not** relabelled as a completely green corrected-guard run. Nevertheless the captured field types, unchanged native tuples, exact original source and pure replay establish the parsing defect.

## Classification and limits of the finding

- **Confirmed:** incorrect expected-identity container/type handling, caused by the JSON pipeline idiom.
- **Confirmed:** incomplete original failure capture; the first deployment guard omitted the expected/observed tuple details needed for diagnosis at that time.
- **Not observed:** native process replacement, native creation-time change or native image change during this session.
- **Not established:** a .NET timestamp-precision defect, foreign executable, security-token mismatch, Windows configuration defect or deployed launcher READY-image regression.
- Corrected per-helper .NET process lookups were **not rerun natively**. Another issue could still be discovered by future fail-closed preflight; this report does not claim otherwise.

## Smallest safe source correction

Deserialize first, then materialize the resulting array in a separate expression:

```powershell
$parsedClaims=ConvertFrom-Json -InputObject $env:ATLAS_AUTH_HELPER_CLAIMS
$claims=@($parsedClaims)
```

The proposed patch additionally refuses empty/non-array/nested input, unexpected or missing fields, non-integer PID/creation values, invalid ranges and empty images **before process lookup**. It also records scalar expected/observed PID, creation and image values privately before a future ownership refusal. It leaves the original native retained-handle checks and exact PID/creation/image predicate unchanged. No timestamp tolerance, path substitution, name-only trust, PID-only acceptance or synthetic operational authority is introduced.

Reviewable source proposal: `docs/QD_HELPER_IDENTITY_GUARD_CORRECTION_V1_2026-11-02.patch`, SHA-256 **6a8811b41213c313ed0a8a87494b5a3a293b8de53c7cc333b4b2d076a5fd2187**. The full proposed orchestration metadata script has canonical SHA-256 **0086db727209dc3ae9e770dec316618296c99d236e07803c8d248cb579613e9f** and remains private alongside the executed original. This is **not applied to an operational installation** and changes none of the nine pinned support-package sources.

## Offline validation

**24 passed / 0 failed**, using the existing Windows PowerShell 5.1 language runtime and captured/synthetic data only. These checks made **zero native process queries**, did not launch an application and were not another native observation session.

Coverage: reproduce legacy nested-array shape and its false creation/image mismatches; preserve every captured scalar; one- and three-claim lists; refuse wrong PID, a **one-tick** creation difference and a different image; preserve the existing case-insensitive image rule; reject empty/null/object/nested/malformed input, missing/extra fields, string PID/creation, array/fractional creation, invalid PID/creation ranges and empty image.

The authoritative offline JSON records all 24 case results. Its console projection displayed null summary properties because an ordered dictionary was piped to `Select-Object`; the persisted JSON was independently read and confirmed **24/0**. This display issue does not alter any case result and is not represented as native acceptance.

## Cleanup, resources and preservation

The private Job had **zero active processes** at completion; Job/worker handles closed, the query child exited, and **no forced termination** was used. The native session's final evidence footprint, including its result file, was **16 entries / 1,540,797 logical bytes / 1,606,333 accounted bytes**. All were below the authorized limits. Subsequent offline analysis and repository checkpoint documentation are retained separately.

No installation, selector provisioning, release selection, Control Center/dashboard/HTTP host, provider, financial activation, PAPER/live trading, service control, Windows Time/configuration change, desktop modification or Genesis access occurred. Existing executed failure evidence was not overwritten. The original application/support pins, unrelated research edit, historical failures, all 21 decisions, seven phases and B1/C1/D1/E1 remain preserved.

## Next authorization and remaining blocker

The diagnostic grant is consumed. The source correction is understood and validated offline; **corrected native helper comparison remains unverified**. That comparison can be a mandatory pre-effect gate in a **fresh explicitly authorized exact bounded nonfinancial deployment**, rather than requiring another accounting implementation or application recopy. It must capture scalar expected/observed values, refuse any genuine mismatch, and pass before installation, selector provisioning or launch.

No operational retry is authorized here. A future approval must name the corrected orchestration proposal while retaining the exact reviewed application/support destinations and pins, all original fresh clock/native/resource checks, **600 seconds / 8,192 entries / 64 MiB**, two provider-disabled Open/Stop cycles and unchanged eight-second Stop. Any remaining native mismatch must stop that future run without mutation. No Windows configuration change or external-reviewer approval is required by this parser correction.

**PAPER: NO. Production: NO-GO.**
