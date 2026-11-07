"""Offline validation of Windows launch parameters."""

import sys
from pathlib import Path

import pytest

from scripts.observation_runtime.personal_native_launch_contract import (
    CREATE_SUSPENDED,
    build_launch_contract,
    validate_launch_command,
)


def test_valid_python_executable():
    executable = str(Path(sys.executable).resolve())

    contract = build_launch_contract([executable, "-V"])

    assert contract["application_name"] == executable
    assert contract["creation_flags"] == CREATE_SUSPENDED
    assert contract["inherit_handles"] is False
    assert contract["shell"] is False


def test_arguments_preserved():
    executable = str(Path(sys.executable).resolve())

    contract = build_launch_contract(
        [executable, "-c", "print('hello world')"]
    )

    assert contract["arguments"][2] == "print('hello world')"


@pytest.mark.parametrize("command", [
    [],
    "python -V",
    None,
    [""],
    ["python.exe", "-V"],
    ["cmd.exe", "/c", "echo hello"],
    ["powershell.exe", "-Command", "exit"],
])
def test_invalid_commands_rejected(command):
    with pytest.raises(ValueError):
        validate_launch_command(command)


def test_missing_executable_rejected():
    with pytest.raises(ValueError):
        validate_launch_command([
            r"C:\AtlasMissingExecutable\missing.exe",
        ])


def test_no_process_creation_imports():
    import inspect
    import scripts.observation_runtime.personal_native_launch_contract as module

    source = inspect.getsource(module)

    assert "CreateProcessW(" not in source
    assert "subprocess.Popen(" not in source


def test_authorized_launch_contract():
    from scripts.observation_runtime.personal_native_launch_contract import (
        build_authorized_launch_contract,
    )

    executable = str(Path(sys.executable).resolve())

    contract = build_authorized_launch_contract(
        [executable, "-V"],
        executable,
    )

    assert contract["application_name"] == executable
    assert contract["inherit_handles"] is False
    assert contract["creation_flags"] == CREATE_SUSPENDED


def test_authorized_contract_is_immutable():
    from scripts.observation_runtime.personal_native_launch_contract import (
        build_authorized_launch_contract,
    )

    executable = str(Path(sys.executable).resolve())

    contract = build_authorized_launch_contract(
        [executable, "-V"],
        executable,
    )

    with pytest.raises(TypeError):
        contract["inherit_handles"] = True


def test_authorized_launch_rejects_other_executable():
    from scripts.observation_runtime.personal_native_launch_contract import (
        validate_authorized_launch,
    )

    executable = str(Path(sys.executable).resolve())

    with pytest.raises(ValueError):
        validate_authorized_launch(
            [executable, "-V"],
            r"C:\Windows\System32\cmd.exe",
        )


def test_authorized_launch_rejects_invalid_authority():
    from scripts.observation_runtime.personal_native_launch_contract import (
        validate_authorized_launch,
    )

    executable = str(Path(sys.executable).resolve())

    for authority in (None, "", "python.exe"):
        with pytest.raises(ValueError):
            validate_authorized_launch(
                [executable, "-V"],
                authority,
            )


def test_authorized_launch_rejects_null_authority():
    from scripts.observation_runtime.personal_native_launch_contract import (
        validate_authorized_launch,
    )

    executable = str(Path(sys.executable).resolve())

    with pytest.raises(ValueError):
        validate_authorized_launch(
            [executable, "-V"],
            executable + "\\0",
        )


@pytest.mark.parametrize("argument", [
    "-V\x00",
    "\x00-V",
    "before\x00after",
])
def test_embedded_nul_argument_rejected(argument):
    executable = str(Path(sys.executable).resolve())

    with pytest.raises(
        ValueError,
        match="NATIVE_LAUNCH_INVALID_ARGUMENT",
    ):
        validate_launch_command([executable, argument])


def test_embedded_nul_executable_rejected():
    executable = str(Path(sys.executable).resolve())

    with pytest.raises(
        ValueError,
        match="NATIVE_LAUNCH_INVALID_ARGUMENT",
    ):
        validate_launch_command([executable + "\x00", "-V"])
