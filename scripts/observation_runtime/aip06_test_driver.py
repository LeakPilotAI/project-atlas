"""Exact native-fixture pytest output/tmp adapter. No execution at import.

The entry requires an already installed shared guard and explicit pinned source
selection; it cannot turn a bare legacy pytest command into native authority.
"""

import os
import ntpath
from pathlib import Path
import xml.etree.ElementTree as ET
from app.services.paper_financial_replay import digest

from scripts.observation_runtime.aip06_fixture_guard import require_fixture
from scripts.observation_runtime.aip06_harness import ROOTS, need, path_for
from scripts.observation_runtime.aip06_outputs import FixtureDirectories

SELECTION = {
    "tests/test_unified_actual_native_lanes.py": "P",
    "tests/test_unified_source_capacity_native.py": "P",
    "tests/test_qd_unified_shutdown.py": "Q",
    "tests/test_perp_native_shutdown.py": "F",
    "tests/test_personal_native_pipeline_capacity.py": "N",
    "tests/test_personal_owned_stop_timing.py": "T",
}


class GuardedTemps:
    def __init__(self, guard, alias, *, label='pytest'):
        self.guard, self.alias = guard, alias
        self.dirs = FixtureDirectories(guard)
        self.base = self.dirs.create(alias, label)
        self.serial = 0

    def getbasetemp(self):
        self.guard.validate_path(self.base)
        return Path(self.base)

    def mktemp(self, basename, numbered=True):
        need(
            numbered is True and type(basename) is str and len(basename) <= 64,
            "BOUNDED_CREATE_NEW_PYTEST_TMP",
        )
        # FixtureDirectories applies path_for's Windows component/ADS rules.
        self.serial += 1
        path = ntpath.join(self.base, basename + "-" + str(self.serial))
        self.guard.mkdir(path)
        return Path(path)


class GuardedJUnit:
    def __init__(self, guard, path):
        self.guard, self.path = guard, path
        self.rows = []
        self.completed = False

    def pytest_runtest_logreport(self, report):
        need(len(self.rows) < 8192, "JUNIT_CASE_CAPACITY")
        existing = next((r for r in self.rows if r["nodeid"] == report.nodeid), None)
        if existing is None:
            existing = {
                "nodeid": report.nodeid,
                "when": report.when,
                "outcome": "incomplete",
                "seconds": 0,
                "message": "INCOMPLETE_TEST",
                "complete": False,
            }
            self.rows.append(existing)
        existing["seconds"] += report.duration
        if report.when == "teardown":
            existing["complete"] = True
        if (
            report.failed
            or report.skipped
            or report.when == "call"
            and existing["outcome"] == "incomplete"
        ):
            # A failed setup/teardown cannot be overwritten by a passing call.
            if existing["outcome"] != "failed" or report.failed:
                existing.update(
                    when=report.when,
                    outcome=report.outcome,
                    message=str(report.longrepr)[:65536]
                    if report.failed or report.skipped
                    else "",
                )

    def pytest_sessionfinish(self, session, exitstatus):
        need(not self.completed, "JUNIT_PUBLICATION_ONCE_ONLY")
        root = ET.Element("testsuites")
        suite = ET.SubElement(root, "testsuite", name="AIP06_NATIVE_FIXTURE")
        for row in self.rows:
            module, _, name = row["nodeid"].partition("::")
            case = ET.SubElement(
                suite,
                "testcase",
                classname=module.removesuffix(".py").replace("/", "."),
                name=name,
                time=str(row["seconds"]),
            )
            if not row["complete"]:
                ET.SubElement(case, "error").text = "INCOMPLETE_TEST_LIFECYCLE"
            elif row["outcome"] == "failed":
                ET.SubElement(
                    case, "failure" if row["when"] == "call" else "error"
                ).text = row["message"]
            elif row["outcome"] == "skipped":
                ET.SubElement(case, "skipped")
        raw = ET.tostring(root, encoding="utf8", xml_declaration=True)
        need(len(raw) <= 1024**2, "JUNIT_BYTES_CAPACITY")
        self.guard.write(self.path, raw)
        self.completed = True


def run_reviewed_tests(*, modules, junit_leaf, pytest_main=None, case_ids=None):
    guard = require_fixture("native-pytest-driver")
    need(
        type(modules) in (tuple, list)
        and modules
        and len(set(modules)) == len(modules)
        and set(modules) <= set(SELECTION),
        "EXACT_AIP06_PYTEST_SELECTION",
    )
    aliases = {SELECTION[m] for m in modules}
    need(len(aliases) == 1, "ONE_NATIVE_FIXTURE_ROOT_PER_TEST_WORKER")
    if case_ids is not None:
        from scripts.observation_runtime.aip06_acceptance_plan import schedule
        reviewed = {r['source_case'] for r in schedule() if r.get('source_case') is not None}
        need(type(case_ids) in (tuple, list) and case_ids and len(case_ids) == len(set(case_ids))
             and set(case_ids) <= reviewed and {c.split('::')[0] for c in case_ids} == set(modules),
             'EXACT_REVIEWED_SCENARIO_NODE_IDS')
    alias = aliases.pop()
    path = path_for("E", junit_leaf)
    need(
        junit_leaf.endswith(".xml") and ntpath.basename(junit_leaf) == junit_leaf,
        "FIXED_JUNIT_OUTPUT",
    )
    need(
        os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD") == "1"
        and os.environ.get("PYTHONDONTWRITEBYTECODE") == "1",
        "NATIVE_TEST_CACHE_PLUGIN_ISOLATION",
    )
    # Source verification precedes importing pytest or allocating test outputs.
    for module in modules:
        guard.processes.verify_test_source(module)
    if alias not in guard.paths.bound:
        guard.mkdir(ROOTS[alias])
    temps = GuardedTemps(guard, alias, label='pytest' if case_ids is None else 'case-' + digest(list(case_ids))[:32])
    junit = GuardedJUnit(guard, path)
    import pytest

    class TempPlugin:
        @pytest.fixture(scope="session")
        def tmp_path_factory(self):
            return temps

        @pytest.fixture
        def tmp_path(self, request):
            return temps.mktemp(request.node.name[:48])

    if pytest_main is None:
        pytest_main = pytest.main
    args = [
        "-q",
        "-p",
        "no:cacheprovider",
        "-p",
        "no:faulthandler",
        "--capture=sys",
    ] + list(modules if case_ids is None else case_ids)
    if any("unified_actual_native_lanes" in m for m in modules):
        args[1:1] = ["-p", "pytest_asyncio.plugin"]
    code = pytest_main(args, plugins=[TempPlugin(), junit])
    need(junit.completed, "MISSING_DURABLE_GUARDED_JUNIT")
    if case_ids is not None:
        need(code == 0 and {r['nodeid'] for r in junit.rows} == set(case_ids)
             and all(r['complete'] and r['outcome'] == 'passed' for r in junit.rows),
             'EXACT_COMPLETE_SCENARIO_RESULT_REQUIRED')
    return {
        "exit_code": code,
        "junit": path,
        "cases": len(junit.rows),
        "native_acceptance": False,
    }


def main():
    require_fixture("native-pytest-driver-entry")
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--modules", nargs="+", required=True, choices=tuple(SELECTION))
    parser.add_argument("--junit-leaf", required=True)
    args = parser.parse_args()
    return run_reviewed_tests(modules=args.modules, junit_leaf=args.junit_leaf)


if __name__ == "__main__":
    main()
