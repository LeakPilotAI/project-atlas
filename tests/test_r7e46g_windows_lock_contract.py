"""Windows cross-process lock contract tests."""

import multiprocessing
import os
import sys
import time

import pytest


pytestmark = pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows locking contract",
)


def lock_worker(path, queue, hold_seconds):
    import msvcrt

    with open(path, "a+b") as stream:
        stream.seek(0)
        if stream.read(1) == b"":
            stream.seek(0)
            stream.write(b"\0")
            stream.flush()

        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            queue.put("acquired")
            time.sleep(hold_seconds)
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def test_windows_lock_blocks_second_process(tmp_path):
    import msvcrt

    path = tmp_path / "collector.lock"
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()

    process = context.Process(
        target=lock_worker,
        args=(str(path), queue, 1.5),
    )

    process.start()

    try:
        assert queue.get(timeout=5) == "acquired"

        with open(path, "r+b") as stream:
            stream.seek(0)

            with pytest.raises(OSError):
                msvcrt.locking(
                    stream.fileno(),
                    msvcrt.LK_NBLCK,
                    1,
                )

        process.join(timeout=5)
        assert process.exitcode == 0

        with open(path, "r+b") as stream:
            stream.seek(0)
            msvcrt.locking(
                stream.fileno(),
                msvcrt.LK_NBLCK,
                1,
            )
            stream.seek(0)
            msvcrt.locking(
                stream.fileno(),
                msvcrt.LK_UNLCK,
                1,
            )
    finally:
        if process.is_alive():
            process.join(timeout=3)

        if process.is_alive():
            pytest.fail(
                "Lock worker did not exit; preserved for diagnosis."
            )