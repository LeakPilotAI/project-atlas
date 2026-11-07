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
    prior_qualification = None
    prior_metadata = None
    identity_overlap = []
    for index in range(cycles):
        if index:
            await sleep(interval_seconds)
        result = await collector()
        current = result.pop('scan_qualification_by_ticker', None)
        metadata = result.pop('scan_listing_metadata', None)
        if isinstance(current, dict) and all(
            isinstance(k, str) and isinstance(v, bool) for k, v in current.items()
        ):
            if prior_qualification is not None:
                shared = set(prior_qualification) & set(current)
                moved_pages = None
                same_page = None
                current_only_created_times_present = None
                if (isinstance(prior_metadata, dict) and isinstance(metadata, dict)
                    and set(prior_metadata) == set(prior_qualification)
                    and set(metadata) == set(current)
                    and all(isinstance(v, dict) and type(v.get('page')) is int
                            and 1 <= v['page'] <= 5 for v in
                            list(prior_metadata.values()) + list(metadata.values()))):
                    moved_pages = sum(prior_metadata[t]['page'] != metadata[t]['page'] for t in shared)
                    same_page = len(shared) - moved_pages
                    current_only_created_times_present = sum(
                        isinstance(metadata[t].get('created_time'), str)
                        for t in set(current) - set(prior_qualification))
                identity_overlap.append({
                    'shared_moved_page': moved_pages,
                    'shared_same_page': same_page,
                    'current_only_with_created_time': current_only_created_times_present,
                    'current_only_are_confirmed_new_listings': False,
                    'from_cycle': index, 'to_cycle': index + 1,
                    'shared_tickers': len(shared),
                    'prior_only_tickers': len(set(prior_qualification) - set(current)),
                    'current_only_tickers': len(set(current) - set(prior_qualification)),
                    'shared_remained_qualified': sum(prior_qualification[t] and current[t] for t in shared),
                    'shared_lost_qualification': sum(prior_qualification[t] and not current[t] for t in shared),
                    'shared_gained_qualification': sum(not prior_qualification[t] and current[t] for t in shared),
                    'shared_remained_unqualified': sum(not prior_qualification[t] and not current[t] for t in shared),
                })
            prior_qualification = current
            prior_metadata = metadata
        else:
            prior_qualification = None
            prior_metadata = None
        observations.append(result)
        if result.get('provider_errors'):
            break
    # Aggregate trends remain useful, but only identity overlap establishes
    # whether an individual contract changed eligibility between two scans.
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
            'listing_identity_overlap': identity_overlap,
            'listing_identity_overlap_not_measured': not bool(identity_overlap),
            'qualification_change_cause_unverified': True,
            'cycles_completed': len(observations), 'observations': observations,
            'analysis': analyzer(), 'orders_placed': 0, 'paper_trades_opened': 0,
            'unattended_runtime_started': False}


if __name__ == '__main__':
    print(json.dumps(asyncio.run(run()), sort_keys=True))