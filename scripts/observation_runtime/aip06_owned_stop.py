"""Connect the existing three-slot QD timing entry to native session/Stop ports."""

import copy
import ntpath

from scripts.observation_runtime.aip06_harness import ROOTS, need
from scripts.observation_runtime.aip06_stop import RetainedFinancialReply


def original_qd_parameters():
    """Original in-memory fixture definitions, never native account evidence."""
    from test_personal_paper_inception_memory import system

    fixture = system("QUALITY_DIPS")
    try:
        return {
            "account_id": fixture.n["account_id"],
            "manifest": copy.deepcopy(fixture.m),
        }
    finally:
        fixture.ledger.db.close()


class OwnedStopAssembly:
    def __init__(self, port, collector, *, fixture_parameters=original_qd_parameters):
        need(
            callable(fixture_parameters), "ORIGINAL_FIXTURE_PARAMETER_PROVIDER_REQUIRED"
        )
        self.port, self.collector, self.parameters = port, collector, fixture_parameters
        self.specs = {}
        self.active = None

    def spec(self, sample, root, nonce, repo):
        need(
            sample in (1, 2, 3)
            and sample not in self.specs
            and root == ROOTS[f"S{sample}"]
            and ntpath.basename(root).endswith(nonce),
            "EXACT_OWNED_STOP_SLOT",
        )
        original = self.parameters()
        need(
            type(original) is dict and set(original) == {"account_id", "manifest"},
            "ORIGINAL_FIXTURE_ACCOUNT_PARAMETERS",
        )
        # Native identity is deliberately absent until the real READY readback.
        account = {**copy.deepcopy(original), "native_source": None}
        expected = {"QUALITY_DIPS": account}
        reader = RetainedFinancialReply()
        spec = {
            "argv": [
                self.port.executable,
                "-B",
                self.port.controller.profile["targets"]["financial_worker"],
            ],
            "options": {
                "env": {
                    "ATLAS_PERSONAL_PIPELINE_TEST_ROOT": root,
                    "ATLAS_SYNTHETIC_STOP_NONCE": nonce,
                    "ATLAS_PERSONAL_STOP_PROFILE": "COMPLETE_FINANCIAL_STOP",
                }
            },
            "expected_accounts": expected,
            "reader": reader,
            "operation_id": f"AIP06-STOP-{sample}-{nonce}",
        }
        self.specs[sample] = {
            "spec": spec,
            "root": root,
            "nonce": nonce,
            "ready": None,
            "sample": sample,
        }
        self.active = self.specs[sample]
        return spec

    def ready(self, child, *, timeout):
        need(
            self.active is not None and self.active["ready"] is None,
            "ONE_CURRENT_NATIVE_READY",
        )
        message = self.port.protocol.financial_ready(child.child, timeout=timeout)
        identity = child.identity()
        native = message["value"]["native"]
        manifest = message["value"]["manifest"]
        need(
            message.get("phase") == "READY"
            and message.get("timing_channel") == self.active["nonce"]
            and type(message.get("identity")) is dict
            and message["identity"].get("pid") == identity["pid"]
            and message["identity"].get("creation_filetime") == identity["created"]
            and ntpath.normcase(message["identity"].get("image", ""))
            == ntpath.normcase(identity["image"])
            and manifest
            == self.active["spec"]["expected_accounts"]["QUALITY_DIPS"]["manifest"]
            and native["account_id"]
            == self.active["spec"]["expected_accounts"]["QUALITY_DIPS"]["account_id"]
            and native["epoch"] == manifest["epoch"],
            "CURRENT_FINANCIAL_READY_SCOPE",
        )
        for role, resource in native["resources"].items():
            path = ntpath.join(self.active["root"], "account", role)
            need(resource["path"] == path, "NATIVE_READY_RESOURCE_ESCAPE")
            actual = self.port.io.inspect(path)
            need(
                actual is not None
                and actual["id"] == resource["native_id"]
                and actual["kind"] == "directory"
                and not actual["reparse"]
                and actual["links"] == 1,
                "CURRENT_FINANCIAL_READY_NATIVE_IDENTITY",
            )
        self.active["spec"]["expected_accounts"]["QUALITY_DIPS"]["native_source"] = (
            copy.deepcopy(native["resources"]["source"]["native_id"])
        )
        self.active["ready"] = copy.deepcopy(message)

    def send(self, child, request):
        need(
            self.active is not None and self.active["ready"] is not None,
            "NO_STOP_BEFORE_GENUINE_FINANCIAL_READY",
        )
        # Revision is the original entry/partial READY cut, not a guessed final
        # revision; the final financial revision is independently replayed.
        revision = self.active["ready"]["value"].get("source_revision")
        need(
            type(revision) is int and revision >= 0,
            "FINANCIAL_READY_CURRENT_REVISION_REQUIRED",
        )
        self.collector.send(child, request, revision=revision)

    def collect(self, child, guard, request, *, deadline_ns):
        need(
            self.active is not None and self.active["ready"] is not None,
            "OWNED_STOP_READY_CONTEXT_REQUIRED",
        )
        spec = self.active["spec"]

        def value():
            return {
                **self.port.protocol.readback_input(
                    child.child, request, deadline_ns=deadline_ns
                ),
                "request": request,
            }

        return self.collector.collect(
            child,
            guard,
            request,
            deadline_ns=deadline_ns,
            reader_argv=[
                self.port.executable,
                "-B",
                self.port.controller.profile["targets"]["readonly_reader"],
            ],
            reader_options={},
            reader_input=value,
            reader=spec["reader"],
        )
