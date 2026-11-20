# Project Atlas — R23 real Windows previous-writer exit recovery repair

**November 18, 2026 | MADDOG | Desktop Commander | SOURCE-ONLY FIX — NOT DEPLOYED | PAPER OFF, LIVE OFF**

## Result: genuine native Windows recovery defect identified and corrected in development source

The immutable selected R23 source `8463f1da3786647677629ae10da5e95c8940e688` has a prior-writer exclusion problem. Its original `verify_previous_exited` uses the R15 `_windows_handle_identity` helper, which requires both Win32 GetProcessTimes and QueryFullProcessImageNameW. On a **genuinely terminated child**, Windows continued to return PID and creation FILETIME but rejected the image lookup (error 31). Consequently the real selected R23 original `verify_previous_exited` **refused the exited process**. This was reproduced with a harmless genuine selected R23 Python child on MADDOG; the original also correctly refused while the child was alive.

The development-only repair in `scripts/observation_runtime/personal_writer_generation.py` adds a **narrow terminated-handle fallback**. It only admits the known R15 missing-image query error when all of the following independent Win32 facts hold: original process-handle PID equals the journal's previous PID, WaitForSingleObject confirms **signaled exit**, GetProcessTimes independently succeeds, and creation FILETIME equals the original previously enrolled creation FILETIME. All other image-query errors, live/ambiguous process states, unavailable GetProcessTimes, creation mismatch, incomplete native enumeration, wrong PID or malformed previous image refuse. The recovered image is NEVER invented from a claim; the prior accepted generation remains the historical binding. Original installed module was not edited.

## Actual real native Windows comparison

- Windows query before exit: `GetProcessTimes=true`, `QueryFullProcessImageNameW=true`, `WaitForSingleObject=258` (alive).
- Windows query after natural exit of **the same** temporary native R23 Python child: `GetProcessTimes=true`, `QueryFullProcessImageNameW=false`, Windows error **31**, `WaitForSingleObject=0` (signaled exit), same PID and creation FILETIME.
- Original selected installed R23 exclusion wrapper: native child live refusal **correct**, native child exited proof **REFUSED**; root cause traced to inherited R15 helper's image-only assumption.
- Patched workspace source running under **genuine original selected R23 Python -I -B -S**: live process correctly **REFUSED**; same process after natural exit **ACCEPTED** as `ORIGINAL_PROCESS_EXITED_NATIVE_CROSSCHECK`. Child exited normally and no financial worker was started.
- Actual native source-only proof: `logs/diagnostics/atlas-r23-native-writer-exclusion-20261118-r01/actual-native-exit-workspace-fixed-proof.json` SHA-256 `4d5457b30a6d24a536e1cb37e4f4566e8ff02ce0b023ca1980f4b99dbcea3e3e`.

## Bounded offline regression and independent preservation

The final **145 distinct Python tests passed, zero failed/skipped**, using original native R23 interpreter with explicit workspace module paths, `-I -B -S`, original two-CPU `NativeR17CpuBudget`, and D-only basetemp. Four original suites: writer generation, two-account owner continuity, Hyperliquid current readback, and original self-Job. Newly tested terminated-image fallback has positive case plus wrong PID, live process, wrong creation FILETIME, failed native times and unrelated Win32 error refusal. Additional prior-image validation rejects malformed/non-D process images. Scoped Ruff **F** passed and `git diff --check` passed. Full unscoped Ruff contains legacy style warnings outside this fix; no unrelated autoformat was performed.

- JUnit `logs/diagnostics/atlas-r23-native-writer-exclusion-20261118-r01/focused-r23-writer-exit-tests-v2.xml` SHA-256 `4039322049d480ab72377aac49d4c7ea5ee471d2e19315be2479b51f37997a36`.
- Patched workspace source SHA-256 `0410338a7b3e213a1ab891e9db28bed0105498e1a25ed60fa3fe8bf397c51874`.
- Final test file SHA-256 `6139b33573f66e915e6a174f5b34446cb108cc82adee5244e4f0287b496752b3`.
- Actual selected immutable R23 installed writer-generation module **UNCHANGED** SHA-256 `1dee7b0754320a25216646a4b898596b7cf180153e118443eca46850cb0784cb`.
- Original selector r0023.json **UNCHANGED** SHA-256 `28960b08a8cbca3d5ed8db37369c5aef5a234f45487e1379c67bba2bdc9d3abc`.
- Independent selected R23 isolated native attestation SHA-256 `3c5b2f060e56751c65cbd8e6c7e8c560fa20d20912bc015d6c7373111b1010ae`, at `logs/diagnostics/atlas-r23-native-writer-exclusion-20261118-r01/final-r23-writer-exit-source-only-attestation.json`. Verified 145 JUnit cases, actual real native live refusal and exited acceptance, twelve original distinct EMPTY financial namespaces, ten protected original hashes intact, E1 accepted 0/3. No r0024 created.

## Production status and next gate

**This only verifies a previous-owner *exclusion mechanism*.** It is NOT a new live 12-role financial owner, original 1,000 USD/1,000 USDC account inception, real Stop/FLAT, market data source permission, financial operator decision, production writer generation or supervised Hyperliquid session. No native account/approval/activation file was written. The original R23 is selected and unmodified; source-only fixes (including this and the Alpaca R23 IEX compatibility repair) require separately approved successor build/install/selection before operational use.

Stage A original provider rights/funding/fees remain **0/3 accepted**, the two real simulated accounts **0/2**, retained financial owner **NOT commissioned**, Stop/FLAT **NOT accepted**, supervised PAPER pilot **NOT started**. No live-money trading, provider credentials or market requests were used; no C-drive Atlas scratch, paid data, VPS, automatic startup or unnecessary child was retained. Existing three protected dirty R23 PIN installer/select/recovery edits are untouched.

**Financial PAPER production NO-GO.** Next technical priority is consolidated exact candidate/qualification and the authentic source/financial activation evidence, not another nominal test-only PASS.
