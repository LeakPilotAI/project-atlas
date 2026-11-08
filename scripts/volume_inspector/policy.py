"""Host-side fail-closed plan builder. Contains NO lifecycle execution API."""

import hashlib
import json
import re
import time
from datetime import datetime
from pathlib import Path

EXPECTED = {
    "postgres": ("c955b8647bb6c18a30e42a7506fa1b6c45f7b1837275d49297bacc6f1c0f11c1", "projectatlas_atlas_pgdata", "/var/lib/postgresql/data", "atlas_pgdata"),
    "redis": ("13617d3155a2b3f4c6184a380892acf544de02e21b7c783c85a0de4b63e9c193", "projectatlas_atlas_redis", "/data", "atlas_redis"),
}
ROOT = "D:\\Work\\Project Atlas"


def plan(service, before, after, image_digest, now=None):
    now = time.time() if now is None else now
    times = [x["observed_unix"] for x in (before, after)]
    if any(type(t) not in (int, float) or not 0 <= now - t <= 5 for t in times) or times[0] > times[1]:
        raise ValueError("Missing, stale, future or unordered evidence")
    a = {k: v for k, v in before.items() if k != "observed_unix"}
    b = {k: v for k, v in after.items() if k != "observed_unix"}
    if service not in EXPECTED or json.dumps(a, sort_keys=True) != json.dumps(b, sort_keys=True):
        raise ValueError("Unknown or changed ownership")
    cid, volume, destination, logical = EXPECTED[service]
    c, v = before["container"], before["volume"]
    created = datetime.fromisoformat(v["CreatedAt"].replace("Z", "+00:00"))
    if created.tzinfo is None:
        raise ValueError("Volume creation identity missing timezone")
    if before["backend"] != "STOPPED" or before["pending"] is not False:
        raise ValueError("Lifecycle state ambiguous")
    labels = {"project": "projectatlas", "service": service, "project.working_dir": ROOT,
              "project.config_files": ROOT + "\\docker-compose.yml", "oneoff": "False"}
    if c["Id"] != cid or c["Labels"] != labels or c["Running"] is not False or c["State"] != "exited" or type(c["Pid"]) is not int or c["Pid"] != 0:
        raise ValueError("Container not conclusively owned and stopped")
    if len(c["Mounts"]) != 1:
        raise ValueError("Extra mounts")
    m = c["Mounts"][0]
    if m["Name"] != volume or m["Destination"] != destination or m["Type"] != "volume":
        raise ValueError("Mount mismatch")
    path = "/var/lib/docker/volumes/" + volume + "/_data"
    if m["Source"] != path or v["Name"] != volume or v["Driver"] != "local" or v["Options"] not in (None, {}) or v["Mountpoint"] != path:
        raise ValueError("Volume mapping mismatch")
    if v["Labels"].get("com.docker.compose.project") != "projectatlas" or v["Labels"].get("com.docker.compose.volume") != logical:
        raise ValueError("Volume ownership missing")
    if before["consumers"] != [cid + "|exited"]:
        raise ValueError("Unknown writer")
    if re.fullmatch(r"sha256:[0-9a-f]{64}", image_digest) is None:
        raise ValueError("Immutable image digest required")
    lock = json.loads(Path(__file__).with_name("helper-image-lock.json").read_text())
    if image_digest != lock["proposed_manifest_digest"]:
        raise ValueError("Image differs from pinned helper descriptor")
    source = Path(__file__).with_name("helper.py").read_bytes()
    if "sha256:" + hashlib.sha256(source).hexdigest() != lock["source_digest"]:
        raise ValueError("Helper source changed after image pinning")
    return {"executable": False, "requires_separate_approval": True,
            "image": image_digest, "service": service,
            "mounts": [{"type": "volume", "source": volume, "target": "/inspection", "readonly": True, "volume_nocopy": True}],
            "network": "none", "cap_drop": ["ALL"], "privileged": False,
            "read_only_rootfs": True, "user": "0:0", "cpus": "0.25", "memory": "128m",
            "memory_swap": "128m", "pids_limit": 16, "ulimit_nofile": 64,
            "no_new_privileges": True, "restart": "no", "pull": "never", "auto_remove": False,
            "helper_alarm_seconds": 30, "operator_deadline_seconds": 40,
            "output_limit_bytes": 65536,
            "entrypoint": ["python3", "-I", "-B", "/opt/atlas-inspector/helper.py", service]}


def verify_controls(actual, expected):
    """Strict normalized-runtime evidence checker, not a Docker executor."""
    keys = {"image", "service", "mounts", "network", "cap_drop", "privileged",
            "read_only_rootfs", "user", "cpus", "memory", "memory_swap", "pids_limit",
            "ulimit_nofile", "no_new_privileges", "restart", "auto_remove", "entrypoint"}
    if set(actual) != keys or json.dumps(actual, sort_keys=True) != json.dumps({k: expected[k] for k in keys}, sort_keys=True):
        raise ValueError("Runtime controls missing, extra or changed")
    return True
