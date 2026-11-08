"""Offline Windows suspended-process launch contract.

Does not invoke CreateProcessW or launch native processes.
"""

import os
import subprocess
from pathlib import Path

CREATE_SUSPENDED = 0x00000004


def validate_launch_command(command):
    """Validate an exact executable and argument vector."""
    if not isinstance(command, (list, tuple)) or not command:
        raise ValueError("NATIVE_LAUNCH_INVALID_COMMAND")

    if not all(
        isinstance(item, str)
        and item
        and "\x00" not in item
        for item in command
    ):
        raise ValueError("NATIVE_LAUNCH_INVALID_ARGUMENT")

    executable = Path(command[0])

    if not executable.is_absolute():
        raise ValueError("NATIVE_LAUNCH_REQUIRES_ABSOLUTE_EXECUTABLE")

    if executable.suffix.lower() != ".exe":
        raise ValueError("NATIVE_LAUNCH_REQUIRES_EXE")

    if not executable.is_file():
        raise ValueError("NATIVE_LAUNCH_EXECUTABLE_NOT_FOUND")

    return tuple(command)


def build_launch_contract(command):
    """Return immutable, validated Windows launch parameters."""
    validated = validate_launch_command(command)

    return {
        "application_name": validated[0],
        "command_line": subprocess.list2cmdline(validated),
        "creation_flags": CREATE_SUSPENDED,
        "inherit_handles": False,
        "shell": False,
        "arguments": validated,
    }


def validate_authorized_launch(command, authorized_executable):
    """Require the exact explicitly authorized executable.

    This is an offline policy check, not a Windows identity guarantee.
    """
    validated = validate_launch_command(command)

    if not isinstance(authorized_executable, str):
        raise ValueError("NATIVE_LAUNCH_INVALID_AUTHORITY")  # noqa: TRY004 - stable public refusal API.

    if not authorized_executable or "\x00" in authorized_executable:
        raise ValueError("NATIVE_LAUNCH_INVALID_AUTHORITY")

    authorized = Path(authorized_executable)

    if not authorized.is_absolute() or not authorized.is_file():
        raise ValueError("NATIVE_LAUNCH_INVALID_AUTHORITY")

    actual = os.path.normcase(os.path.abspath(validated[0]))
    expected = os.path.normcase(os.path.abspath(authorized_executable))

    if actual != expected:
        raise ValueError("NATIVE_LAUNCH_EXECUTABLE_NOT_AUTHORIZED")

    return validated


def build_authorized_launch_contract(command, authorized_executable):
    """Build a read-only launch contract for one authorized executable."""
    from types import MappingProxyType

    validated = validate_authorized_launch(
        command,
        authorized_executable,
    )

    return MappingProxyType({
        "application_name": validated[0],
        "command_line": subprocess.list2cmdline(validated),
        "creation_flags": CREATE_SUSPENDED,
        "inherit_handles": False,
        "shell": False,
        "arguments": validated,
    })
