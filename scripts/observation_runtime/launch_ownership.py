"""Retained-handle launch evidence, never an operational startup authority.

No discovery-based adoption: the caller must retain the original parent and
launch handles, explicitly specify direct or one-redirector topology, and supply
an independent native observer. JSON/PID/command claims alone cannot bind.
"""

import re
from dataclasses import dataclass


class OwnershipRefused(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise OwnershipRefused(reason)


def identity(row):
    require(type(row) is dict, "NATIVE_OBSERVATION_REQUIRED")
    for key in ("pid", "created"):
        require(
            type(row.get(key)) is int and row[key] > 4,
            "SCALAR_NATIVE_IDENTITY_REQUIRED",
        )
    require(
        type(row.get("image")) is str and bool(row["image"]), "EXACT_IMAGE_REQUIRED"
    )
    require(
        type(row.get("file_id")) is tuple
        and len(row["file_id"]) == 3
        and all(type(v) is int for v in row["file_id"]),
        "NATIVE_IMAGE_FILE_ID_REQUIRED",
    )
    require(
        type(row.get("sha256")) is str and re.fullmatch("[0-9a-f]{64}", row["sha256"]),
        "EXACT_IMAGE_HASH_REQUIRED",
    )
    return tuple(row[k] for k in ("pid", "created", "image", "file_id", "sha256"))


@dataclass(frozen=True)
class LaunchRequest:
    role: str
    nonce: str
    topology: str
    launch_image: tuple  # (canonical native path, native file identity, SHA-256)
    runtime_image: tuple
    launch_command: str
    runtime_command: str
    auxiliary_image: tuple | None = None
    auxiliary_command: str | None = None
    auxiliary_exit_code: int | None = None

    def validate(self):
        require(
            self.role in ("acceptance_supervisor", "acceptance_worker"),
            "EXPLICIT_HELPER_ROLE_REQUIRED",
        )
        require(
            type(self.nonce) is str and re.fullmatch("[0-9a-f]{32}", self.nonce),
            "LAUNCH_NONCE_REQUIRED",
        )
        require(
            self.topology in ("direct", "one_redirector"), "EXPLICIT_TOPOLOGY_REQUIRED"
        )
        for image in (self.launch_image, self.runtime_image):
            require(type(image) is tuple and len(image) == 3, "PINNED_IMAGE_REQUIRED")
            identity(
                {
                    "pid": 5,
                    "created": 5,
                    "image": image[0],
                    "file_id": image[1],
                    "sha256": image[2],
                }
            )
        for command in (self.launch_command, self.runtime_command):
            require(
                type(command) is str
                and 0 < len(command) < 32767
                and "\0" not in command,
                "EXACT_COMMAND_REQUIRED",
            )
        if self.topology == "direct":
            require(
                self.launch_image == self.runtime_image
                and self.launch_command == self.runtime_command,
                "DIRECT_REQUEST_CONTRADICTION",
            )
        if self.auxiliary_image is not None:
            require(
                self.topology == "one_redirector",
                "EXPLICIT_AUXILIARY_TOPOLOGY_REQUIRED",
            )
            image = self.auxiliary_image
            require(
                type(image) is tuple and len(image) == 3,
                "PINNED_AUXILIARY_IMAGE_REQUIRED",
            )
            identity(
                {
                    "pid": 5,
                    "created": 5,
                    "image": image[0],
                    "file_id": image[1],
                    "sha256": image[2],
                }
            )
            require(
                type(self.auxiliary_command) is str
                and bool(self.auxiliary_command)
                and "\0" not in self.auxiliary_command,
                "EXACT_AUXILIARY_COMMAND_REQUIRED",
            )
            require(
                type(self.auxiliary_exit_code) is int
                and self.auxiliary_exit_code in (0, 109),
                "EXPLICIT_AUXILIARY_TERMINAL_CODE_REQUIRED",
            )
        else:
            require(
                self.auxiliary_command is None and self.auxiliary_exit_code is None,
                "UNBOUND_AUXILIARY_COMMAND",
            )


class RetainedLaunchBinding:
    """An in-memory capability fences lifetimes with original native handles.

    api.observe must independently cross-check live handle PID/creation/image
    against command/ancestry observations. api.members returns the complete
    bounded native Job roster. Handle ownership stays with the caller on every
    success or refusal; this object never closes, kills or reopens by PID.
    """

    def __init__(self, api, request, parent_handle, launch_handle):
        request.validate()
        require(
            parent_handle is not None and launch_handle is not None,
            "ORIGINAL_HANDLES_REQUIRED",
        )
        self.api, self.request = api, request
        self.parent_handle, self.launch_handle = parent_handle, launch_handle
        self.runtime_handle = None
        self.auxiliary_handle = None
        self.refused = False
        self.finished = False
        self.descendant_graph = None
        self.parent = api.observe(parent_handle)
        self.launch = api.observe(launch_handle)
        identity(self.parent)
        self._match(
            self.launch, request.launch_image, request.launch_command, self.parent
        )

    @staticmethod
    def _match(row, expected_image, command, parent):
        identity(row)
        require(
            tuple(row[k] for k in ("image", "file_id", "sha256")) == expected_image,
            "EXECUTABLE_IDENTITY_MISMATCH",
        )
        require(row.get("command_line") == command, "COMMAND_LINE_MISMATCH")
        require(
            type(row.get("parent_pid")) is int and row["parent_pid"] == parent["pid"],
            "PARENT_IDENTITY_MISMATCH",
        )
        require(row["created"] >= parent["created"], "PARENT_LIFETIME_MISMATCH")

    def _live(self):
        parent = self.api.observe(self.parent_handle)
        require(parent == self.parent, "PARENT_IDENTITY_OR_LIFETIME_CHANGED")
        launch = self.api.observe(self.launch_handle)
        require(launch == self.launch, "LAUNCH_IDENTITY_OR_LIFETIME_CHANGED")
        return parent, launch

    def bind_runtime(self, runtime_handle, ready, auxiliary_handle=None):
        require(
            not self.refused and not self.finished and self.runtime_handle is None,
            "ONE_USE_BINDING_REQUIRED",
        )
        try:
            require(runtime_handle is not None, "RETAINED_RUNTIME_HANDLE_REQUIRED")
            parent, launch = self._live()
            runtime = self.api.observe(runtime_handle)
            expected_parent = parent if self.request.topology == "direct" else launch
            self._match(
                runtime,
                self.request.runtime_image,
                self.request.runtime_command,
                expected_parent,
            )
            same = identity(runtime) == identity(launch)
            require(same == (self.request.topology == "direct"), "TOPOLOGY_MISMATCH")
            require(
                type(ready) is dict
                and ready
                == {
                    "pid": runtime["pid"],
                    "nonce": self.request.nonce,
                    "role": self.request.role,
                },
                "READY_REQUEST_MISMATCH",
            )
            expected = {launch["pid"], runtime["pid"]}
            if self.request.auxiliary_image is not None:
                require(
                    auxiliary_handle is not None, "RETAINED_AUXILIARY_HANDLE_REQUIRED"
                )
                auxiliary = self.api.observe(auxiliary_handle)
                self._match(
                    auxiliary,
                    self.request.auxiliary_image,
                    self.request.auxiliary_command,
                    runtime,
                )
                require(auxiliary["pid"] not in expected, "DISTINCT_AUXILIARY_REQUIRED")
                expected.add(auxiliary["pid"])
            else:
                require(auxiliary_handle is None, "UNAPPROVED_AUXILIARY_HANDLE")
            require(self.api.members() == expected, "UNEXPECTED_OR_MISSING_JOB_PROCESS")
            # Reobserve after the independent roster/READY cut; no cached flags.
            self._live()
            require(
                self.api.observe(runtime_handle) == runtime, "RUNTIME_IDENTITY_CHANGED"
            )
            self.runtime_handle, self.runtime = runtime_handle, runtime
            if auxiliary_handle is not None:
                self.auxiliary_handle, self.auxiliary = auxiliary_handle, auxiliary
            return self.verify()
        except Exception:
            self.refused = True
            raise

    def verify(self):
        require(
            not self.refused and not self.finished and self.runtime_handle is not None,
            "ACTIVE_BOUND_LIFETIME_REQUIRED",
        )
        try:
            self._live()
            require(
                self.api.observe(self.runtime_handle) == self.runtime,
                "RUNTIME_IDENTITY_CHANGED",
            )
            rows_to_verify = [self.launch, self.runtime]
            if self.auxiliary_handle is not None:
                require(
                    self.api.observe(self.auxiliary_handle) == self.auxiliary,
                    "AUXILIARY_IDENTITY_CHANGED",
                )
                rows_to_verify.append(self.auxiliary)
            if self.descendant_graph is not None:
                require(callable(self.descendant_graph), 'RETAINED_DESCENDANT_GRAPH_REQUIRED')
                rows_to_verify.extend(self.descendant_graph())
            require(
                self.api.members() == {v["pid"] for v in rows_to_verify},
                "UNEXPECTED_OR_MISSING_JOB_PROCESS",
            )
            # Same scalar format as existing metadata guards, but derived only
            # from this fresh retained capability, never accepted from JSON.
            rows = {
                v["pid"]: {k: v[k] for k in ("pid", "created", "image")}
                for v in rows_to_verify
            }
            return [rows[k] for k in sorted(rows)]
        except Exception:
            self.refused = True
            raise

    def verify_exit(self):
        require(
            not self.refused and not self.finished and self.runtime_handle is not None,
            "BOUND_EXIT_EVIDENCE_REQUIRED",
        )
        try:
            require(
                self.api.observe(self.parent_handle) == self.parent,
                "PARENT_LOST_OR_ORPHANED",
            )
            children = [
                (self.launch_handle, self.launch),
                (self.runtime_handle, self.runtime),
            ]
            if self.auxiliary_handle is not None:
                children.append((self.auxiliary_handle, self.auxiliary))
            for handle, row in children:
                native = self.api.lifecycle(handle)
                require(
                    native
                    == {
                        "pid": row["pid"],
                        "created": row["created"],
                        "exited": True,
                        "exit_code": self.request.auxiliary_exit_code
                        if handle == self.auxiliary_handle
                        else 0,
                    },
                    "EXACT_NORMAL_EXIT_REQUIRED",
                )
            require(self.api.members() == set(), "JOB_NOT_DRAINED")
            self.finished = True
            return {
                "normal_exit": True,
                "job_empty": True,
                "handles_still_retained": True,
                "operational_startup_authorized": False,
            }
        except Exception:
            self.refused = True
            raise
