"""R7E47X: synthetic-only lifecycle adapter; no network or trading."""

from scripts.observation_runtime.bootstrap import (
    Status,
    SyntheticRuntime,
)
from scripts.observation_runtime.contracts import Action, Refused
from scripts.observation_runtime.r7e47w_runner import (
    SyntheticObservationRunner,
)


class SessionRefused(RuntimeError):
    """Controlled synthetic session operation refused."""


class ControlledSyntheticSession:
    """Connect an admitted R7E47S runtime to an R7E47W fixture runner."""

    def __init__(
        self,
        runtime: SyntheticRuntime,
        runner: SyntheticObservationRunner,
    ):
        if type(runtime) is not SyntheticRuntime:
            raise SessionRefused("Exact synthetic runtime required")
        if type(runner) is not SyntheticObservationRunner:
            raise SessionRefused("Exact synthetic runner required")

        bootstrap = runtime.bootstrap
        if (
            bootstrap._runtime is not runtime
            or bootstrap.world.runtime_alive is not True
            or bootstrap.evaluate(continuing=True).status != Status.ADMITTED
        ):
            raise SessionRefused("Active admitted session required")

        if runner.closed:
            raise SessionRefused("Runner already closed")

        manifest = bootstrap.contract.manifest
        if runner.provider not in manifest["data_sources"]:
            raise SessionRefused("Runner provider outside session source scope")

        if runtime._session_managed:
            raise SessionRefused("Runtime already session-managed")
        runtime._session_managed = True
        self.runtime = runtime
        self.runner = runner
        self.closed = False

    def ingest(self, raw: bytes):
        if self.closed:
            raise SessionRefused("Session adapter closed")

        bootstrap = self.runtime.bootstrap
        if (
            bootstrap.world.runtime_alive is not True
            or bootstrap.evaluate(continuing=True).status != Status.ADMITTED
        ):
            raise SessionRefused("Fresh continuing admission required")

        if self.runner.closed:
            raise SessionRefused("Runner closed")

        if self.runner.provider not in bootstrap.contract.manifest["data_sources"]:
            raise SessionRefused("Observation source no longer authorized")

        # The runner consumes a durable attempt before validating fixture bytes.
        # Invalid fixtures must never reach the observation dispatcher.
        snapshot = self.runner.ingest(raw)

        # R7E47S dispatch performs its own fresh admission checks and
        # writes DATA_SOURCE only after an acknowledged synthetic action.
        self.runtime._session_dispatch_permit = True
        try:
            result = self.runtime.execute(
                Action.OBSERVE,
                source=self.runner.provider,
            )
        finally:
            self.runtime._session_dispatch_permit = False

        return snapshot, result

    def stop(self) -> None:
        if self.closed:
            raise SessionRefused("Session adapter already closed")

        self.closed = True
        self.runner.stop()

        # Preserve the original R7E47S graceful/recovery-required decision.
        self.runtime.stop()

    def execute(self, capability: str) -> None:
        raise Refused("Direct capability execution unavailable")