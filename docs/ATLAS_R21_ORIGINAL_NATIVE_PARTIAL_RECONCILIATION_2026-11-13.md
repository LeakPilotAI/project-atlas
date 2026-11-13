# Atlas R21 native partial recovery: original Windows file-by-file reconciliation
Date: 2026-11-13

## Original failure and the independent recovery audit

The original R21 immutable code-only install failed at its 500-second low-impact copy/readback deadline and durably wrote REFUSED_PRESERVE_PARTIAL_NO_RETRY into its existing journal. At failure, 7,350 of the 10,731 pinned original files had been created in the existing protected native D:\AtlasRuntime\releases\119dd8626da32e74bd7f86db9de1c1a8fd2c20ac root, while R20 remained selected and every original financial namespace was empty.

This execution ran scripts/atlas_r21_partial_native_readonly.py against the actual failed native release. It independently revalidated ALL 7,350 already-created native file identities and exact protected owner/SYSTEM ACLs from original Windows NTFS handles, hardlink count one, actual bytes, SHA256 content, unique physical file identities, and an exact prefix of the audited source/dependency inventory. It verified all 915 original native directories, original refused installation journal, pinned original source commit/archive and original selected R20 financial roots. No file in the failed native directory was modified, and no native release receipt or selection was fabricated.

Read-only original audit evidence was saved **create-only** to:
D:\Work\Project Atlas\logs\diagnostics\atlas-r21-native-partial-readonly-audit-20261113.json
Audit SHA256:
039e23789d9d7d83f6003834d92c532bd79f45be1e440e2ab288413febce84d1
Exactly 7,350 prefix files; 217,782,758 bytes; 3,381 source/dependency files remaining.

## Guarded one-time recovery design

The separate scripts/atlas_r21_native_recovery.py implementation is not a retry of the failed installer. It requires a *different*, one-shot Windows SID/source-script hash/original native audit digest/old refusal SHA/target/installed source/r20 predecessor approval and new separate recovery intent journal. Before any new file write, it independently reopens/rechecks every original prefix file using Windows-native handles and compares full identities with the pinned original audit. Only remaining originally **absent** files may be opened for CREATE-EXCLUSIVE, using verified pinned original Python dependency file handles or immutable R21 source archive, original NTFS ACL checks, native identity/size/hash validation and second original-handle file readback. No previously copied file may be opened for writing or overwritten.

After all 10,731 files are verified, it builds an original native installed receipt containing all authentic directory/file identities and invokes the existing isolated, installed-release NativePersonalReleaseIdentity verifier under the actual newly completed D: R21 Python interpreter. Only after successful full independent native readback and reverified original selected R20/12 empty finance namespaces may it create a distinct durable recovery receipt and full code-only release receipt, then append a genuine final verified ACK to the original refusal journal. Its original historical **refusal line is always preserved**. Any partial/unknown recovery outcome is a separate terminal recovery refusal and must not be retried.

The selected R21 code-only release must still have its own independently approved, separately verified immutable selector revision 20. Neither a successful recovery nor later selector creates simulated financial accounts, source/provider rights or PAPER trading authority. Production QD needs real executable valuation provenance and safe epoch rollover. Hyperliquid needs independently verifiable historical settlement oracle + actual fee rights. Original native FS1/FS3 inceptions and Stop-first runtime must then be accepted.

## Protection and storage
All new source, tests, approvals and diagnostics live under the only main project D:\Work\Project Atlas. The incomplete protected native root is an existing identity-bound AtlasRuntime release path and must not be treated as C: or D: scratch. Preserve original R20 and all 12 financial custody root IDs. No VPS, no paid data, no default startup, no LIVE financial orders. Real original native source/data rights cannot be granted by tests or file hashes.
