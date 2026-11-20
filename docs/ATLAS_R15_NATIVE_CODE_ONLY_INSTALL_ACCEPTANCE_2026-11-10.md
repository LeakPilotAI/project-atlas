# Atlas R15 — one-shot code-only native installation accepted (2026-11-10)

## Result: installed and verified, **not selected**, financial PAPER NO-GO

The operator explicitly approved the exact **R15 unselected CODE-ONLY native installation**, with no approval for release selection, provider access, account activation, simulated orders or live trading. The one-shot Windows-SID-bound approval was created once in `logs/diagnostics/atlas-r15-code-only-native-install-one-shot-approval.json`, SHA-256 `0746bcf799af2a5b6069511b2de15ead45650f58db97eff729ce37154148986a`. The installer consent contract bound the exact source archive, dependency inventory, installer-source digest, native release target, original R14 head and local operator identity; it forbade selection, finance, account, provider and startup authority.

Before installing, two potentially irreversible source defects were found and fixed: the native copier requires its `prepared["started"]` monotonic deadline marker **before** the create-only intent; and pinning the approval SHA must preserve a canonical installer source digest without a self-referential file hash. Pre-approval regression: **74 passed, zero failed**. Fix commit: `c5ad7f03`; exact one-shot source-pinned approval commit: `07e0e6f3`. Canonical approved installer source SHA-256 `7a16b28b5a7df2d26fc508a3d7b00dab453f61dfe08951bb736cdb2e3612c103`.

The installer then executed **once**. It passed its independent Google+Cloudflare two-peer native-clock qualification, native selected-R14 and host resource preflights, and performed a single bounded low-priority Windows native file copy and independent installed-child readback. The OS reported the active installer Python worker at **Idle** priority. The source-only frozen R15 input archive was not rebuilt; no source/dependency tampering or R14 selection mutation occurred.

### Exact installed code evidence

| Item | Verified result |
|---|---|
| R15 source commit | `2c79a8d846d6b33669008114732ae5896153812a` |
| Frozen source archive SHA-256 | `f6cb597a53373efee929c306ae42537e16abcbcf6e57f7bd23ee92e8570160c0` |
| Installed native target | `D:\AtlasRuntime\releases\2c79a8d846d6b33669008114732ae5896153812a` |
| Installed files / directories | **10,526 files / 912 directories** |
| Installed Python version | **3.12**, verified by child startup |
| Immutable create-only final receipt | `logs/diagnostics/qd-unselected-release-2c79a8d846d6b33669008114732ae5896153812a.json` |
| Final receipt SHA-256 | `b313a20f0a747c4a2ac81a2c1ae11b50901786008ce75f84202bf2f2435e741c` |
| Native installed artifact digest | `6db8cae881cd0f331b3f0aae78c92f27dbff860c658bb67ab1cfe91a6b8465e6` |
| Terminal install journal | `logs/diagnostics/qd-unselected-release-2c79a8d846d6b33669008114732ae5896153812a.pending.jsonl` |
| Journal acceptance | Exactly two records; terminal `UNSELECTED_CODE_INSTALL_VERIFIED` has final receipt SHA-256 above, verified by the existing `release_selection.validate_native_install_ack` |
| Native-selected release (unchanged) | **R14**, revision 13, `r0013.json` SHA-256 `6b1e04b8f733d46421c81a5d158dbafbecf052e6f3a8e8289d175caca96d4e31` |
| Derived *proposal*, not published | Revision 14 proposed head `274f5b00ee0e2f6271c6dd1dc5316f7d9124e932483038a6d93ef62ddbd2cd25` |
| Real `r0014.json` | **Absent**; no selection occurred |

Independent post-install read-only `atlas_r15_selection_handoff.inspect()` validated the complete canonical receipt, all native file/directory entries, its content-digest chain, the original two-entry create-only journal and exact selected R14 parent, then produced the deterministic **proposal only** for future R15 code selection. A subsequent dedicated read-only regression `tests/test_atlas_r15_native_code_installed_postacceptance.py` passed **6 tests, zero failures**.

The installation approval pin was reset to **`APPROVAL_SHA256 = None`** after success. The exact one-shot approval record is retained as audit evidence, but the code-only installer refuses further execution. The separate R15 code selection publisher still has `APPROVAL_SHA256=None`. The R14 original selection remains unchanged. Current Hyperliquid public request budget remains **10 used of 12; 2 available**, with no market requests consumed.

Create-only machine-readable acceptance record: `docs/ATLAS_R15_NATIVE_CODE_ONLY_INSTALL_ACCEPTANCE_2026-11-10.json`, SHA-256 `8f1f798126189e23baaca1a7e92228c1f9089ef8736c286439d0e16acb6b06a9`.

### Remaining boundary

**Next release delivery action:** separately review/authorize exact **one-shot code-only R15 selection**, using revision-14 proposal `274f5b00...` and independently reopened native installed original handles. Do **not** interpret today's installation consent as selection authority, and do **not** rerun any part of the now-complete installation.

**Next financial operating work:** independent actual PAPER account and Quality Dips/Hyperliquid financial writer enrollment; approved source freshness/rights (Alpaca IEX and Hyperliquid), independent continuous clock/ledger and supervised real simulated session including Stop/flat/restart. Kalshi's newly listed YES/NO strategy remains separately uncommissioned. Desktop financial Start/Stop stays blocked until accepted. No VPS/paid data, Windows boot changes, Project Genesis writes, account credentials or real trading.

**Financial PAPER remains NO-GO, 0/9 independent gates accepted.** Installed code is not an operating PAPER session and is not evidence of profitability.
