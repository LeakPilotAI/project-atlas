"""Perpetual PAPER enrollment structure; validity is never acceptance authority."""
import ntpath

from app.investment.quality_dips_operational_contract import exact, hashed, native_id, process
from app.services.paper_financial_replay import body, strict, text

ROLES = ("source", "projection", "report", "control", "coordination", "custody")
WRITERS = ("decision", "source", "projection", "report", "coordination", "funding", "mark")


def validate_enrollment(value):
    e = strict(body(value))
    exact(e, "PERP_AUTO_NATIVE_ENROLLMENT_V1", {
        "profile", "account_id", "epoch", "policy_digest", "inception_digest",
        "release_digest", "resources", "writers", "clock_source", "acceptance_id",
    })
    if e["profile"] != "AUTONOMOUS_PAPER_ONLY_V1":
        raise ValueError("PERP_PAPER_PROFILE_REQUIRED")
    for key in ("account_id", "epoch", "clock_source", "acceptance_id"):
        text(e[key])
    for key in ("policy_digest", "inception_digest", "release_digest"):
        hashed(e[key])
    if type(e["resources"]) is not dict or set(e["resources"]) != set(ROLES):
        raise ValueError("PERP_COMPLETE_RESOURCE_ROSTER_REQUIRED")
    paths, ids = [], []
    for resource in e["resources"].values():
        exact(resource, "PERP_AUTO_NATIVE_ROOT_V1", {"path", "native_id"})
        native_id(resource["native_id"])
        path = resource["path"]
        if (type(path) is not str or not path.startswith("D:\\") or len(path) > 1024
                or any(c in path[2:] for c in (":", "%", "\x00", "/"))
                or any(p in ("", ".", "..") for p in path[3:].split("\\"))):
            raise ValueError("PERP_D_ONLY_EXACT_PATH_REQUIRED")
        paths.append(ntpath.normcase(path))
        ids.append(body(resource["native_id"]))
    if (len(set(paths)) != len(ROLES) or len(set(ids)) != len(ROLES)
            or any(a != b and b.startswith(a + "\\") for a in paths for b in paths)):
        raise ValueError("PERP_RESOURCE_ALIAS_REFUSED")
    if type(e["writers"]) is not dict or set(e["writers"]) != set(WRITERS):
        raise ValueError("PERP_COMPLETE_WRITER_ROSTER_REQUIRED")
    for writer in e["writers"].values():
        process(writer)
        if not writer["image"].startswith("D:\\"):
            raise ValueError("PERP_D_ONLY_EXECUTABLE_REQUIRED")
    return e
