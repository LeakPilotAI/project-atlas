"""Offline deterministic image descriptors; NOT an image pull/build/load.

Base layers are deliberately absent. A descriptor bundle is not a usable image.
Hydration and independent image/container acceptance require separate approval.
"""

import hashlib
import io
import json
import tarfile
from pathlib import Path


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def assemble(base_manifest, base_config, source):
    manifest = json.loads(base_manifest)
    if digest(base_config) != manifest["config"]["digest"]:
        raise ValueError("Base config digest mismatch")
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        info = tarfile.TarInfo("opt/atlas-inspector/helper.py")
        info.size, info.mode, info.uid, info.gid, info.mtime = len(source), 0o444, 0, 0, 0
        tar.addfile(info, io.BytesIO(source))
    # Uncompressed OCI tar avoids gzip/zlib/platform-dependent byte streams.
    layer = stream.getvalue()
    config = json.loads(base_config)
    if len(config["rootfs"]["diff_ids"]) != len(manifest["layers"]):
        raise ValueError("Base layer count mismatch")
    config["created"] = "1970-01-01T00:00:00Z"
    config["config"] = {"Env": ["PATH=/usr/local/bin:/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE=1"],
                        "Entrypoint": ["python3", "-I", "-B", "/opt/atlas-inspector/helper.py"],
                        "User": "0:0", "WorkingDir": "/", "Labels": {"org.atlas.inspector.source": digest(source)}}
    config["rootfs"]["diff_ids"].append(digest(stream.getvalue()))
    config["history"] = [{"created": "1970-01-01T00:00:00Z", "created_by": "pinned-base"} for _ in config["rootfs"]["diff_ids"]]
    raw_config = canonical(config)
    result = {"schemaVersion": 2, "mediaType": "application/vnd.oci.image.manifest.v1+json",
              "config": {"mediaType": "application/vnd.oci.image.config.v1+json", "digest": digest(raw_config), "size": len(raw_config)},
              "layers": manifest["layers"] + [{"mediaType": "application/vnd.oci.image.layer.v1.tar", "digest": digest(layer), "size": len(layer)}]}
    raw_manifest = canonical(result)
    return raw_manifest, raw_config, layer


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    out = Path(args.output)
    out.mkdir(exist_ok=False)
    lock = json.loads((root / "base-image-lock.json").read_text())
    base_manifest = (root / "base-manifest.json").read_bytes()
    base_config = (root / "base-config.json").read_bytes()
    if digest(base_manifest) != lock["platform_manifest_digest"]:
        raise ValueError("Base manifest changed")
    blobs = assemble(base_manifest, base_config, (root / "helper.py").read_bytes())
    for name, raw in zip(["helper-manifest.json", "helper-config.json", "helper-layer.tar"], blobs):
        (out / name).write_bytes(raw)
    (out / "descriptor-status.json").write_text(json.dumps({"manifest_digest": digest(blobs[0]),
        "image_available": False, "base_layers_included": False, "runtime_verified": False,
        "source_digest": digest((root / "helper.py").read_bytes())}, indent=2))
    print(digest(blobs[0]))


if __name__ == "__main__":
    main()
