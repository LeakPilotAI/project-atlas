"""Inert selected-lane request validation. No execution dependencies or approval path."""
from app.services.paper_runtime_boundary import PaperBoundaryRefused


class PaperWriteRequestContract:
    def __init__(self, *, strategy, epoch):
        if strategy not in ("QUALITY_DIPS", "HYPERLIQUID_MANUAL") or type(epoch) is not str or not epoch:
            raise ValueError("Explicit selected-lane fixture binding required")
        self.strategy, self.epoch = strategy, epoch

    def submit(self, request):
        required = {"schema", "strategy", "epoch", "operation_id", "action", "position_id",
                    "expected_source_revision", "expected_source_head", "receipt_schema"}
        if type(request) is not dict or set(request) != required:
            raise PaperBoundaryRefused("MALFORMED_REQUEST")
        if (request["schema"] != "PAPER_WRITE_REQUEST_INERT_V1" or request["receipt_schema"] != "PAPER_RECEIPT_FIXTURE_V1"
                or request["strategy"] != self.strategy or request["epoch"] != self.epoch
                or request["action"] not in ("ENTRY", "PARTIAL_EXIT", "FULL_EXIT")
                or type(request["expected_source_revision"]) is not int or request["expected_source_revision"] < 0
                or type(request["operation_id"]) is not str or not request["operation_id"].startswith(self.epoch + ":")
                or len(request["operation_id"]) <= len(self.epoch) + 1):
            raise PaperBoundaryRefused("MISMATCHED_REQUEST")
        head = request["expected_source_head"]
        if type(head) is not str or len(head) != 64 or any(c not in "0123456789abcdef" for c in head):
            raise PaperBoundaryRefused("SOURCE_EXPECTATION_MISSING")
        position = request["position_id"]
        if (request["action"] == "ENTRY" and position is not None) or (request["action"] != "ENTRY" and
                (type(position) is not str or not position.startswith(self.epoch + ":") or len(position) <= len(self.epoch) + 1)):
            raise PaperBoundaryRefused("POSITION_BINDING_MISMATCH")
        # Syntactically valid expectation is not an accepted epoch or financial authority.
        raise PaperBoundaryRefused("EXECUTION_DISABLED: no financial activation or registered writer")
