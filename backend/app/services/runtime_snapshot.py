"""Single-flight read models with immediate last-good responses during refresh."""
import asyncio
import time


class RuntimeSnapshot:
    def __init__(self, ttl=10):
        self.ttl = ttl
        self.value = None
        self.updated = 0.0
        self.last_attempt = 0.0
        self.task = None
        self.loop = None
        self.refreshes = 0
        self.duration_ms = 0.0
        self.error = None

    async def get(self, build, warming, budget=0.2):
        loop = asyncio.get_running_loop()
        if self.loop is not loop:
            self.loop, self.task, self.value, self.updated = loop, None, None, 0.0
            self.last_attempt, self.error = 0.0, None
        if self.task is None and time.monotonic() - self.last_attempt >= self.ttl:
            self.last_attempt = time.monotonic()
            self.task = asyncio.create_task(self._refresh(build))
        if self.value is None and self.task is not None:
            try:
                await asyncio.wait_for(asyncio.shield(self.task), budget)
            except asyncio.TimeoutError:
                pass
        result = dict(self.value if self.value is not None else warming)
        result['runtime_refresh'] = {
            'state': 'WARMING' if self.value is None else ('STALE' if self.task or self.error else 'FRESH'),
            'refreshing': self.task is not None, 'age_sec': round(time.monotonic()-self.updated, 2) if self.value else None,
            'duration_ms': self.duration_ms, 'refreshes': self.refreshes, 'error': self.error,
        }
        return result

    async def _refresh(self, build):
        started = time.monotonic()
        try:
            self.value = await build()
            self.updated = time.monotonic()
            self.error = None
        except Exception as exc:
            self.error = type(exc).__name__
            # Keep the last-good timestamp honest; last_attempt bounds retries.
        finally:
            self.duration_ms = round((time.monotonic()-started)*1000, 2)
            self.refreshes += 1
            self.task = None
