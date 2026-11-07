"""Explicitly invoked bounded read-only Kalshi observation session; no background service."""
from __future__ import annotations

import asyncio
import json

from scripts.kalshi_forward_quote_observer import collect
from scripts.kalshi_forward_quote_analysis import analyze


async def run(*, cycles: int = 2, interval_seconds: float = 60.0,
              collector=collect, analyzer=analyze, sleep=asyncio.sleep) -> dict:
    if not isinstance(cycles, int) or not 1 <= cycles <= 3:
        raise ValueError('cycles must be 1 to 3')
    if not isinstance(interval_seconds, (int, float)) or not 1 <= interval_seconds <= 300:
        raise ValueError('interval must be between 1 and 300 seconds')
    observations = []
    for index in range(cycles):
        if index:
            await sleep(interval_seconds)
        result = await collector()
        observations.append(result)
        if result.get('provider_errors'):
            break
    return {'session': 'OPERATOR_INVOKED_READ_ONLY_BOUNDED',
            'cycles_completed': len(observations), 'observations': observations,
            'analysis': analyzer(), 'orders_placed': 0, 'paper_trades_opened': 0,
            'unattended_runtime_started': False}


if __name__ == '__main__':
    print(json.dumps(asyncio.run(run()), sort_keys=True))