"""Bounded, read-only stack samples when the API event loop stops yielding."""
import asyncio
import sys
import threading
import time
from collections import deque


class RuntimeWatchdog:
    def __init__(self):
        self.samples = deque(maxlen=8)
        self._stop = threading.Event()
        self._thread = None
        self._task = None
        self._last_tick = 0.0

    async def start(self):
        self._stop.clear()
        self._last_tick = time.monotonic()
        self._loop_thread = threading.get_ident()
        self._task = asyncio.create_task(self._heartbeat())
        self._thread = threading.Thread(target=self._sample, daemon=True)
        self._thread.start()

    async def _heartbeat(self):
        while True:
            self._last_tick = time.monotonic()
            await asyncio.sleep(0.25)

    def _sample(self):
        while not self._stop.wait(1):
            lag = time.monotonic() - self._last_tick
            if lag < 1:
                continue
            frame = sys._current_frames().get(self._loop_thread)
            stack = []
            while frame is not None and len(stack) < 16:
                # No locals, source text, request values, or credentials.
                stack.append({"file": frame.f_code.co_filename,
                              "line": frame.f_lineno,
                              "function": frame.f_code.co_name})
                frame = frame.f_back
            self.samples.append({"lag_ms": round(lag * 1000, 3), "stack": stack})

    async def stop(self):
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def snapshot(self):
        return list(self.samples)


runtime_watchdog = RuntimeWatchdog()
