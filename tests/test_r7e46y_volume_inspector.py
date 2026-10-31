"""Synthetic metadata fixtures only; never calls Docker or production paths."""

import copy
import importlib.util
import io
import json
import stat
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts/volume_inspector" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


helper, policy = load("helper"), load("policy")
assembler = load("assemble_descriptor")
PIN = json.loads((ROOT / "scripts/volume_inspector/helper-image-lock.json").read_text())["proposed_manifest_digest"]


class Entries:
    def __init__(self, entries): self.items = entries
    def __enter__(self): return iter(self.items)
    def __exit__(self, *args): pass


class SyntheticTree:
    def __init__(self, items):
        self.items = items
        self.opened = []
        self.released = []

    def root_stat(self): return meta(stat.S_IFDIR, inode=0)

    def visit(self, parent, name, expected=None):
        path = "" if parent is None else (parent + "/" + name).strip("/")
        self.opened.append(path)
        return path

    def entries(self, fd):
        value = self.items[fd]
        if isinstance(value, Exception): raise value
        return Entries(value)

    def metadata(self, entry): return entry[0], entry[1]
    def readlink(self, fd, name): return "../../outside/secret-credential"
    def release(self, fd): self.released.append(fd)


def meta(mode, size=10, inode=1):
    return SimpleNamespace(st_mode=mode, st_size=size, st_dev=1, st_ino=inode, st_blocks=1)


def fixture(service="postgres"):
    cid, volume, dest, logical = policy.EXPECTED[service]
    path = "/var/lib/docker/volumes/" + volume + "/_data"
    return {"observed_unix": time.time(), "backend": "STOPPED", "pending": False, "consumers": [cid + "|exited"],
            "container": {"Id": cid, "Labels": {"project": "projectatlas", "service": service,
                "project.working_dir": policy.ROOT, "project.config_files": policy.ROOT + "\\docker-compose.yml", "oneoff": "False"},
                "Running": False, "State": "exited", "Pid": 0,
                "Mounts": [{"Name": volume, "Type": "volume", "Destination": dest, "Source": path}]},
            "volume": {"CreatedAt": "2026-10-01T00:00:00Z", "Name": volume, "Driver": "local", "Options": None, "Mountpoint": path,
                "Labels": {"com.docker.compose.project": "projectatlas", "com.docker.compose.volume": logical}}}


def test_inventory_and_no_file_opens():
    tree = SyntheticTree({"": [("base", meta(stat.S_IFDIR)), ("PG_VERSION", meta(stat.S_IFREG, 5))],
                          "base": [("secret-table-name", meta(stat.S_IFREG, 20, 2))]})
    result = helper.inspect(tree, "postgres")
    assert result["files"] == 2 and result["logical_file_bytes"] == 25
    assert result["directories"] == 1 and result["layout"] == ["base"]
    assert result["status"] == "METADATA_COMPLETE_COVERAGE_UNPROVEN"
    assert "secret-table-name" not in json.dumps(result)
    assert tree.opened == ["", "base"]


def test_external_link_never_followed_or_leaked():
    tree = SyntheticTree({"": [("pg_wal", meta(stat.S_IFLNK))]})
    result = helper.inspect(tree, "postgres")
    assert result["status"] == "BLOCKED_EXTERNAL_REFERENCE"
    assert tree.opened == [""]
    assert "secret-credential" not in json.dumps(result)
    assert result["links"][0]["scope"] == "external_unfollowed"


def test_internal_link_classified_without_traversal():
    value = helper.link_metadata("pg_wal", "/var/lib/postgresql/data/wal", "postgres")
    assert value["scope"] == "internal_unfollowed"
    assert "target_sha256" in value and "wal" not in value["target_sha256"]


def test_unknown_allocation_never_reported_as_zero():
    s = meta(stat.S_IFREG)
    del s.st_blocks
    value = helper.inspect(SyntheticTree({"": [("x", s)]}), "redis")
    assert value["allocated_file_bytes"] is None and value["tree_allocated_bytes"] is None


def test_hardlinks_count_entries_but_deduplicate_bytes():
    s = meta(stat.S_IFREG, size=100, inode=2)
    value = helper.inspect(SyntheticTree({"": [("x", s), ("y", s)]}), "redis")
    assert value["files"] == 2 and value["logical_file_bytes"] == 100
    assert value["allocated_file_bytes"] == 512


@pytest.mark.parametrize("bad", ["", "not-a-date", "2026-10-01T00:00:00"])
def test_volume_creation_identity_required(bad):
    f = fixture()
    f["volume"]["CreatedAt"] = bad
    with pytest.raises(ValueError): policy.plan("postgres", f, f, PIN)


@pytest.mark.parametrize("case", ["entries", "permission", "timeout", "special", "depth", "badname"])
def test_incomplete_is_not_capacity_success(case):
    tree = SyntheticTree({"": [("x", meta(stat.S_IFREG))]})
    kwargs = {}
    if case == "entries": kwargs["limit"] = 0
    elif case == "permission": tree.items[""] = PermissionError("sensitive path")
    elif case == "timeout": kwargs["deadline"] = 0
    elif case == "special": tree.items[""] = [("fifo", meta(stat.S_IFIFO))]
    elif case == "badname": tree.items[""] = [("../escape", meta(stat.S_IFREG))]
    else:
        for depth in range(35): tree.items["/".join(["x"] * depth)] = [("x", meta(stat.S_IFDIR))]
    result = helper.inspect(tree, "redis", **kwargs)
    assert result["status"] == "INCOMPLETE" and result["anomalies"]
    assert "sensitive path" not in json.dumps(result)


def test_output_limit_remains_valid_json():
    result = json.loads(helper.bounded_json({"x": "a" * 70000}))
    assert result["status"] == "INCOMPLETE" and result["reason"] == "OUTPUT_LIMIT"


@pytest.mark.parametrize("options", ["rw", "rw,nosuid", ""])
def test_rw_mount_rejected(options):
    with pytest.raises(RuntimeError): helper.verify_mountinfo(f"1 0 1:1 / /inspection {options} - ext4 x rw")


def test_ro_mount_and_nested_mount_protection():
    line = "1 0 1:1 / /inspection ro,nosuid - ext4 x rw"
    helper.verify_mountinfo(line)
    with pytest.raises(RuntimeError): helper.verify_mountinfo(line + "\n2 1 1:1 / /inspection/nested ro - ext4 x ro")


@pytest.mark.parametrize("service", ["postgres", "redis"])
def test_exact_plan_and_resources(service):
    f = fixture(service)
    p = policy.plan(service, f, copy.deepcopy(f), PIN)
    assert p["mounts"][0]["readonly"] and p["mounts"][0]["volume_nocopy"]
    assert len(p["mounts"]) == 1 and p["network"] == "none"
    assert p["cap_drop"] == ["ALL"] and not p["privileged"]
    assert p["cpus"] == "0.25" and p["memory"] == p["memory_swap"] == "128m"
    assert p["pids_limit"] == 16 and p["helper_alarm_seconds"] == 30
    assert not p["executable"] and not p["auto_remove"]


@pytest.mark.parametrize("case", ["missing", "id", "project", "pid", "running", "volume", "consumer", "pending", "changed", "digest"])
def test_ownership_or_identity_change_blocks(case):
    before = fixture()
    if case == "missing": del before["container"]["Labels"]
    elif case == "id": before["container"]["Id"] = "b" * 64
    elif case == "project": before["container"]["Labels"]["project"] = "other"
    elif case == "pid": before["container"]["Pid"] = False
    elif case == "running": before["container"]["Running"] = True
    elif case == "volume": before["volume"]["Labels"] = {}
    elif case == "consumer": before["consumers"].append("unknown|running")
    elif case == "pending": before["pending"] = True
    after = copy.deepcopy(before)
    if case == "changed": after["container"]["Id"] = "c" * 64
    with pytest.raises((KeyError, ValueError)):
        policy.plan("postgres", before, after, "latest" if case == "digest" else PIN)


def test_missing_optional_signal_is_irrelevant():
    f = fixture()
    assert policy.plan("postgres", f, f, PIN)


@pytest.mark.parametrize("stamp", [None, True, float("nan"), float("inf"), 990, 1001])
def test_stale_missing_future_evidence_refused(stamp):
    f = fixture()
    f["observed_unix"] = stamp
    with pytest.raises(ValueError): policy.plan("postgres", f, f, PIN, now=1000)


@pytest.mark.parametrize("field", ["mounts", "network", "cap_drop", "cpus", "memory", "pids_limit", "privileged", "read_only_rootfs", "entrypoint"])
def test_runtime_control_changes_refused(field):
    f = fixture()
    p = policy.plan("postgres", f, f, PIN)
    keys = {"image", "service", "mounts", "network", "cap_drop", "privileged", "read_only_rootfs", "user", "cpus", "memory", "memory_swap", "pids_limit", "ulimit_nofile", "no_new_privileges", "restart", "auto_remove", "entrypoint"}
    actual = {k: p[k] for k in keys}
    assert policy.verify_controls(actual, p)
    actual[field] = None
    with pytest.raises(ValueError): policy.verify_controls(actual, p)


def test_descriptor_reproducible_and_tamper_evident():
    folder = ROOT / "scripts/volume_inspector"
    manifest, config, source = [(folder / p).read_bytes() for p in ["base-manifest.json", "base-config.json", "helper.py"]]
    a = assembler.assemble(manifest, config, source)
    assert a == assembler.assemble(manifest, config, source)
    assert assembler.digest(a[0]) == PIN
    assert a[0] != assembler.assemble(manifest, config, source + b"\n")[0]


def test_descriptor_rejects_changed_base_config():
    folder = ROOT / "scripts/volume_inspector"
    with pytest.raises(ValueError):
        assembler.assemble((folder / "base-manifest.json").read_bytes(), b"{}", b"synthetic")


def test_public_blob_corruption_preserves_partial_without_success(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "assemble_descriptor", assembler)
    materializer = load("materialize_oci")
    monkeypatch.setattr(sys, "argv", ["materializer", "--output", str(tmp_path / "artifact")])
    monkeypatch.setattr(materializer, "fetch", lambda url, headers: io.BytesIO(b'{"token":"synthetic"}' if "auth.docker.io" in url else b"corrupt"))
    with pytest.raises(ValueError): materializer.main()
    assert list((tmp_path / "artifact/blobs/sha256").glob("*.partial"))
    assert not (tmp_path / "artifact/assembly-result.json").exists()
    assert not (tmp_path / "artifact/index.json").exists()


@pytest.mark.skipif(sys.platform != "linux", reason="Actual Linux fd backend requires separately approved Linux/container acceptance")
def test_actual_linux_descriptor_backend(tmp_path):
    (tmp_path / "PG_VERSION").write_text("synthetic")
    tree = helper.PosixTree(str(tmp_path))
    try: assert helper.inspect(tree, "postgres")["files"] == 1
    finally: tree.close()
