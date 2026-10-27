"""Dependency-injected V5 containment lifecycle.

OFFLINE DESIGN IMPLEMENTATION ONLY.

No Windows API adapter is connected.
No native process execution is authorized.
"""


class ContainedChild:
    """Owns the process and Job Object handles after successful admission."""

    def __init__(self, api, job, process):
        self.api = api
        self.job = job
        self.process = process
        self.closed = False

    def close(self):
        if self.closed:
            return

        errors = []

        # Explicitly attempt termination of this owned Job Object first.
        if self.job is not None:
            try:
                self.api.terminate_job(self.job)
            except Exception as exc:  # noqa: BLE001 - preserve ownership after any adapter failure.
                errors.append(f"terminate_job: {exc}")

        # Continue cleanup even if termination or another close fails.
        for name, handle in (
            ("process", self.process),
            ("job", self.job),
        ):
            if handle is None:
                continue

            try:
                self.api.close_handle(handle)
            except Exception as exc:  # noqa: BLE001 - preserve ownership after any adapter failure.
                errors.append(f"close_{name}: {exc}")
            else:
                if name == "process":
                    self.process = None
                else:
                    self.job = None

        self.closed = self.process is None and self.job is None

        if errors:
            raise RuntimeError(
                "NATIVE_JOB_CLEANUP_INCOMPLETE: "
                + "; ".join(errors)
            )


class AdmissionFailure(RuntimeError):
    """Carries every unreleased owned handle for explicit cleanup retry."""

    def __init__(self, message, cleanup):
        super().__init__(message)
        self.cleanup = cleanup


class FailedAdmissionCleanup:
    """Retain an unassigned process until termination succeeds.

    Closing an unrelated/empty Job Object cannot terminate an unassigned
    suspended child. Failed termination must never lose its last process handle.
    """

    def __init__(self, api, job, process, thread, assigned):
        self.api = api
        self.job = job
        self.process = process
        self.thread = thread
        self.assigned = assigned
        self.terminated = process is None
        self.closed = False

    def close(self):
        if self.closed:
            return
        errors = []
        if self.process is not None and not self.terminated and not self.assigned:
            try:
                self.api.terminate_process(self.process)
            except Exception as exc:  # noqa: BLE001 - preserve ownership after any adapter failure.
                errors.append(f"terminate_process: {exc}")
            else:
                self.terminated = True
        if self.job is not None and self.process is not None:
            try:
                self.api.terminate_job(self.job)
            except Exception as exc:  # noqa: BLE001 - preserve ownership after any adapter failure.
                errors.append(f"terminate_job: {exc}")
            else:
                if self.assigned:
                    self.terminated = True
        for name in ("thread", "job", "process"):
            handle = getattr(self, name)
            if handle is None or (name == "process" and not self.terminated):
                continue
            try:
                self.api.close_handle(handle)
            except Exception as exc:  # noqa: BLE001 - preserve ownership after any adapter failure.
                errors.append(f"close_{name}: {exc}")
            else:
                setattr(self, name, None)
                if name == "job" and self.assigned:
                    # Assignment is only recorded after kill-on-close setup.
                    self.terminated = True
        self.closed = all(getattr(self, name) is None
                          for name in ("thread", "process", "job"))
        if errors:
            raise RuntimeError("CLEANUP_INCOMPLETE: " + "; ".join(errors))


def launch_contained_child(api, command):
    """Admit a suspended child only after Job Object assignment.

    Dependency-injected only; the Windows adapter still refuses creation.
    AdmissionFailure.cleanup retains ownership after every failed cleanup.
    """
    job = process = thread = None
    child_assigned = False
    try:
        job = api.create_job()
        api.configure_kill_on_close(job)
        process, thread = api.create_suspended_child(command)
        api.assign_child(job, process)
        child_assigned = True
        api.resume_child(thread)
        api.close_handle(thread)
        thread = None
        return ContainedChild(api, job, process)
    except Exception as exc:
        cleanup = FailedAdmissionCleanup(api, job, process, thread, child_assigned)
        message = "NATIVE_JOB_CONTAINMENT_REQUIRED"
        try:
            cleanup.close()
        except Exception as cleanup_exc:  # noqa: BLE001 - surface cleanup and retain owner.
            message += "; " + str(cleanup_exc)
        raise AdmissionFailure(message, cleanup) from exc
