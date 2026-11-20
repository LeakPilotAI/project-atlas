"""Assemble an OCI artifact from pinned public blobs; never invokes Docker.

Requires explicit --output NEW directory. Downloads public Python base layers
only, streams/hashes with bounded size, preserves partial artifacts on failure.
No source volume, host configuration, Docker socket or credentials are read.
"""

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

from assemble_descriptor import assemble, canonical, digest


def fetch(url, headers):
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    source = Path(__file__).resolve().parent
    out = Path(args.output)
    out.mkdir(exist_ok=False)
    blobs = out / "blobs" / "sha256"
    blobs.mkdir(parents=True)
    base_raw = (source / "base-manifest.json").read_bytes()
    base = json.loads(base_raw)
    pin = json.loads((source / "base-image-lock.json").read_text())
    if digest(base_raw) != pin["platform_manifest_digest"]:
        raise ValueError("Base manifest pin mismatch")
    manifest, config, layer = assemble(base_raw, (source / "base-config.json").read_bytes(), (source / "helper.py").read_bytes())
    lock = json.loads((source / "helper-image-lock.json").read_text())
    if digest(manifest) != lock["proposed_manifest_digest"]:
        raise ValueError("Helper manifest pin mismatch")
    if sum(x["size"] for x in base["layers"]) > 128 * 1024 * 1024:
        raise ValueError("Public artifact download budget exceeded")
    with fetch("https://auth.docker.io/token?service=registry.docker.io&scope=repository:library/python:pull", {}) as reply:
        token = json.loads(reply.read(65536))["token"]
    for item in base["layers"]:
        target = blobs / item["digest"].removeprefix("sha256:")
        partial = target.with_suffix(".partial")
        count, hasher = 0, hashlib.sha256()
        with fetch("https://registry-1.docker.io/v2/library/python/blobs/" + item["digest"], {"Authorization": "Bearer " + token}) as reply, partial.open("xb") as output:
            while block := reply.read(1024 * 1024):
                count += len(block)
                if count > item["size"]:
                    raise ValueError("Public blob exceeds pinned size")
                hasher.update(block)
                output.write(block)
        if count != item["size"] or "sha256:" + hasher.hexdigest() != item["digest"]:
            raise ValueError("Public blob hash/size mismatch")
        partial.rename(target)
    for raw in [manifest, config, layer]:
        with (blobs / digest(raw).removeprefix("sha256:")).open("xb") as stream:
            stream.write(raw)
    (out / "oci-layout").write_bytes(canonical({"imageLayoutVersion": "1.0.0"}))
    (out / "index.json").write_bytes(canonical({"schemaVersion": 2, "manifests": [{
        "mediaType": "application/vnd.oci.image.manifest.v1+json", "digest": digest(manifest),
        "size": len(manifest), "platform": {"os": "linux", "architecture": "amd64"}}]}))
    (out / "assembly-result.json").write_bytes(canonical({"status": "ARTIFACT_COMPLETE_RUNTIME_UNTESTED",
        "manifest_digest": digest(manifest), "public_base_bytes": sum(x["size"] for x in base["layers"]),
        "docker_invoked": False, "runtime_verified": False}))
    print(digest(manifest))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - do not expose redirect/token-bearing URLs.
        raise SystemExit("OCI assembly failed; partial evidence retained; " + type(exc).__name__) from None
