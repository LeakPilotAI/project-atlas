# Atlas metadata inspector — isolated implementation

This directory implements a metadata-only helper, a **non-executable** host
admission plan and deterministic OCI artifact assembly. It is not connected to
Atlas startup, production volumes, backups, trading or notifications.

`helper-image-lock.json` binds the current helper source and immutable OCI
manifest. `base-image-lock.json` pins the public linux/amd64 Python base.
`base-manifest.json` and `base-config.json` are public registry metadata only.

Reproduce descriptors in a **new** isolated output directory:

```text
python scripts/volume_inspector/assemble_descriptor.py --output NEW_DESCRIPTOR_DIRECTORY
```

Explicit public-blob artifact assembly, requiring network/download approval:

```text
python scripts/volume_inspector/materialize_oci.py --output NEW_OCI_DIRECTORY
```

Neither command invokes Docker, imports an image or starts a container. The
second verifies pinned public layer hashes and preserves partial failures.
Existing outputs must never be overwritten. Independent verification should
check every blob/size and uncompressed rootfs diffID before image import.

The helper is Linux-only and accepts exactly `postgres` or `redis`. It never
opens a regular source file. R7E46Z exercised its pinned image, descriptor backend,
read-only mounts and resource controls against synthetic Linux fixtures. See
`docs/R7E46Z_SYNTHETIC_LINUX_RUNTIME_ACCEPTANCE.md` for exact evidence and remaining
blocked guarantees. Production volume execution is still unapproved. Synthetic
plan checks alone are not proof that Docker enforces the controls. No production execution
API is provided; passing a plan or filename inspection does not prove ownership,
continuous writer exclusion, effective configuration or recovery coverage.

Read `docs/R7E46Y_REAL_VOLUME_APPROVAL_PACKAGE.md` before any proposed import or
runtime acceptance. Real-volume execution remains prohibited until separately
approved after Linux synthetic acceptance. Never use database entrypoints,
additional mounts/capabilities, writable source mounts or automatic cleanup.
