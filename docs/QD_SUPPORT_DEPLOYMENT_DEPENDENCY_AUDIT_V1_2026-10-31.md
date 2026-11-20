# Support deployment dependency audit — before implementation

Base: fdfb9a7fd9c63f067f37e5fdd39784dac5d09b1e. Scope: source and confined disposable validation only.

| Dependency | Existing evidence | Initial status / work required |
|---|---|---|
| Exact support source archive | Eight source files plus manifest, 8a2277... / 09b00f...; prior preflight verified | Implemented, retained unchanged as historical package |
| Explicit deployment destination and namespace | Launcher derives launchers/<manifest hash>; old manifest lacks destination | Missing: separate versioned deployment manifest |
| Support installer | Application-only copier and native creation/readback primitives exist | Missing: bounded support adapter reusing native primitives |
| Durable support installation intent, receipt, ACK | Existing application receipt cannot represent support installation | Missing: versioned support receipt, complete native readback and partial refusal |
| Selection-resource provisioning | NativeSelectionStore opens accepted existing resources only | Missing: create-new protected resource and identity evidence, without selecting |
| Atomic selection and rollback | Native immutable journal, shared mutex, append-only rollback; eight genuine fixture cases | Implemented; operational use remains separately gated |
| Installed-only support admission | Exact root, interpreter and file hashes; no workspace fallback | Implemented; add durable support-deployment admission and fixture-only positive path |
| Runtime dependencies | Existing 638-source app and D:-resident Python; required source rows in support manifest | Implemented in frozen app; bind explicit dependency inventory and verify missing components |
| Provider-disabled startup | Audited child, no Session/collectors, no financial mutations, loopback CSP | Implemented; genuine complete disposable installed-path validation required |
| Control Center Open/Close | Retained PowerShell controller and readiness/Stop protocol | Implemented source; positive disposable path and actual process validation required |
| Original dashboard | Existing six surfaces served by read-only host | Implemented; verify deployed origins and unavailable financial state |
| Eight-second Stop and restart | Owned stdin/process protocol, selection lease, cumulative Stop budget | Implemented; genuine complete disposable controller lifecycle measurement required |
| Operational clock | Genuine unchanged LocalWindowsClock, <=1000 ms / <=120 s | Separate live acceptance; no system changes authorized here |
| Operational installation/selection/rollback | None performed | Authorization-gated: never execute in this milestone |
| Financial custody/current research/executable IEX | Separate commissioning gates | Unchanged; no financial or provider authority in this milestone |

Implementation will preserve the frozen application and historical support pins. Any new support payload receives new explicit pins. Disposable acceptance must be labelled DISPOSABLE and cannot satisfy operational enrollment or clock authority. A second audit will record actual completion and residual gaps rather than assume this initial matrix is acceptance.
