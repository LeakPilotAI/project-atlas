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
    # Aggregate scan-level eligibility changes without claiming that the same
    # listings were present across cycles (only aggregate counts are observed).
    eligibility_trend = []
    for index, result in enumerate(observations, start=1):
        screened = result.get('unique_markets_screened')
        qualified = result.get('entry_gate_qualified_new_listings_seen')
        reasons = result.get('rejection_reason_counts')
        if (not isinstance(screened, int) or screened < 0 or
            not isinstance(qualified, int) or not 0 <= qualified <= screened or
            not isinstance(reasons, dict)):
            continue
        eligibility_trend.append({
            'cycle': index, 'screened': screened, 'qualified': qualified,
            'qualified_fraction': qualified / screened if screened else None,
            'volume_rejected': reasons.get('INSUFFICIENT_24H_VOLUME', 0),
            'open_interest_rejected': reasons.get('INSUFFICIENT_OPEN_INTEREST', 0),
        })
    return {'session': 'OPERATOR_INVOKED_READ_ONLY_BOUNDED',
            'eligibility_trend': eligibility_trend,
            'listing_identity_overlap_not_measured': True,
            'qualification_change_cause_unverified': True,
            'cycles_completed': len(observations), 'observations': observations,
            'analysis': analyzer(), 'orders_placed': 0, 'paper_trades_opened': 0,
            'unattended_runtime_started': False}


if __name__ == '__main__':
    print(json.dumps(asyncio.run(run()), sort_keys=True))