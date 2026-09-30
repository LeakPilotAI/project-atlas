"""Bounded, read-only stack samples when the API event loop stops yielding."""
import asyncio
import os
import sys
import threading
import time
from collections import Counter, deque


class RuntimeWatchdog:
    def __init__(self):
        self.samples = deque(maxlen=8)
        self._stop = threading.Event()
        self._thread = None
        self._task = None
        self._last_tick = 0.0
        self.stall_count = 0
        self.max_lag_ms = 0.0
        self.thread_samples = deque(maxlen=60)
        self.task_count = 0
        self.executor_pending = 0

    async def start(self):
        self._stop.clear()
        self._last_tick = time.monotonic()
        self.task_count = len(asyncio.all_tasks())
        self._loop_thread = threading.get_ident()
        self._task = asyncio.create_task(self._heartbeat())
        self._thread = threading.Thread(target=self._sample, daemon=True)
        self._thread.start()

    async def _heartbeat(self):
        while True:
            self._last_tick = time.monotonic()
            self.task_count = len(asyncio.all_tasks())
            executor = getattr(asyncio.get_running_loop(), "_default_executor", None)
            self.executor_pending = executor._work_queue.qsize() if executor else 0
            await asyncio.sleep(0.25)

    def _sample(self):
        while not self._stop.wait(1):
            # Bounded statistical profile: filenames/functions only, never locals.
            active = []
            for frame in sys._current_frames().values():
                for _ in range(24):
                    if frame is None:
                        break
                    filename = frame.f_code.co_filename.replace("\\", "/")
                    if "/app/" in filename and "runtime_watchdog.py" not in filename:
                        active.append((filename.split("/app/", 1)[1], f'{frame.f_code.co_name}:{frame.f_lineno}'))
                        break
                    frame = frame.f_back
            frame = None  # never retain a sampled thread's live locals between ticks
            self.thread_samples.append(active)
            lag = time.monotonic() - self._last_tick
            self.max_lag_ms = max(self.max_lag_ms, round(lag * 1000, 3))
            if lag < 1:
                continue
            self.stall_count += 1
            frame = sys._current_frames().get(self._loop_thread)
            stack = []
            while frame is not None and len(stack) < 16:
                # No locals, source text, request values, or credentials.
                stack.append({"file": frame.f_code.co_filename,
                              "line": frame.f_lineno,
                              "function": frame.f_code.co_name})
                frame = frame.f_back
            frame = None
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

    def metrics(self):
        counts = Counter(item for batch in list(self.thread_samples) for item in batch)
        return {"pid": os.getpid(), "stall_samples": self.stall_count, "max_heartbeat_age_ms": self.max_lag_ms,
                "tasks": self.task_count, "threads": threading.active_count(),
                "executor_pending": self.executor_pending,
                "thread_profile_60s": [{"file": key[0], "function": key[1], "samples": n}
                                       for key, n in counts.most_common(20)]}


runtime_watchdog = RuntimeWatchdog()
