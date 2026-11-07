"""Operator-invoked, read-only forward Kalshi quotes; never creates PAPER trades."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path

from app.prediction.kalshi_public import kalshi_public
from app.prediction.paper_engine import walk_executable_depth
from app.prediction.prediction_paper_automation import PredictionPaperAutomation

DEFAULT_PATH = Path('logs/research/kalshi_new_listing_forward_quotes.jsonl')
# Activity is an entry gate, not a prerequisite for observing new listings.
# Never discard new-market research solely for having low initial volume/OI.
OBSERVATION_ONLY_ACTIVITY_REASONS = frozenset({
    'INSUFFICIENT_24H_VOLUME', 'INSUFFICIENT_OPEN_INTEREST',
})


async def collect(*, path: Path = DEFAULT_PATH, limit: int = 5,
                  quantity: Decimal = Decimal('1'), now: datetime | None = None) -> dict:
    if not isinstance(limit, int) or not 1 <= limit <= 5:
        raise ValueError('limit must be between 1 and 5')
    if not quantity.is_finite() or not Decimal('0') < quantity <= Decimal('10'):
        raise ValueError('invalid diagnostic quantity')
    observed = now or datetime.now(timezone.utc)
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError('observation clock must be timezone aware')
    scanner = PredictionPaperAutomation()
    # Bounded pagination avoids depending on the provider's first page alone.
    # Deduplicate tickers before expensive orderbook reads; no account access.
    candidates = []
    fully_qualified = 0
    seen = set()
    cursor = None
    pages_scanned = 0
    for _ in range(5):
        payload = await asyncio.wait_for(
            kalshi_public.get_markets(status='open', limit=100, cursor=cursor),
            timeout=12,
        )
        pages_scanned += 1
        for market in payload.get('markets', []):
            if not isinstance(market, dict):
                continue
            ticker = str(market.get('ticker') or '').strip().upper()
            if not ticker or ticker in seen:
                continue
            seen.add(ticker)
            reasons = scanner._prefilter_reasons(market, observed)
            if not reasons:
                fully_qualified += 1
            if not set(reasons) - OBSERVATION_ONLY_ACTIVITY_REASONS:
                candidates.append((market, reasons))
        next_cursor = str(payload.get('cursor') or '').strip()
        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
    # Provider pagination order is not a liquidity ranking. Review the entire
    # bounded discovery pool, prioritizing entry-qualified markets, then the
    # strongest observable activity; retain the original entry-gate reasons.
    def activity(market):
        values = market.get('activity') or {}
        def safe(key):
            try:
                value = Decimal(str(values.get(key) or '0'))
                return value if value.is_finite() and value >= 0 else Decimal('0')
            except (ValueError, ArithmeticError):
                return Decimal('0')
        return (min(safe('volume_24h_contracts'), safe('open_interest_contracts')),
                safe('volume_24h_contracts'), safe('open_interest_contracts'))
    candidates.sort(key=lambda pair: (not not pair[1],
                                       *(-value for value in activity(pair[0])),
                                       str(pair[0].get('ticker') or '')))
    # Reserve a small portion of each bounded sample for previously unseen
    # listings. Keep the remaining slots for repeat quotes needed to measure
    # forward movement. Historical records are research data, never authority.
    observed_tickers = set()
    if path.exists():
        with path.open(encoding='utf-8') as history:
            for line in history:
                try:
                    prior = json.loads(line)
                except (ValueError, TypeError):
                    continue
                if isinstance(prior, dict) and prior.get('schema') == 'kalshi-forward-quote-v1':
                    ticker = prior.get('ticker')
                    if isinstance(ticker, str):
                        observed_tickers.add(ticker.upper())
    qualified = [pair for pair in candidates if not pair[1]]
    exploratory = [pair for pair in candidates if pair[1]]
    # When the qualified pool exceeds the quote budget, reserve room for
    # previously unseen qualified listings while retaining a repeat for
    # longitudinal measurement. Never downgrade qualified entry gates.
    qualified_repeated = [pair for pair in qualified if pair[0]['ticker'].upper() in observed_tickers]
    qualified_new = [pair for pair in qualified if pair[0]['ticker'].upper() not in observed_tickers]
    if len(qualified) >= limit and qualified_new:
        repeat_slots = min(len(qualified_repeated), 1 if limit > 1 else 0)
        selected = qualified_repeated[:repeat_slots] + qualified_new[:limit - repeat_slots]
        if len(selected) < limit:
            selected.extend(qualified_repeated[repeat_slots:repeat_slots + limit - len(selected)])
    else:
        selected = qualified[:limit]
    remaining = limit - len(selected)
    if remaining:
        new = [pair for pair in exploratory if pair[0]['ticker'].upper() not in observed_tickers]
        repeated = [pair for pair in exploratory if pair[0]['ticker'].upper() in observed_tickers]
        # At least one repeat when available, to preserve longitudinal pairs.
        repeat_slots = min(len(repeated), 1 if remaining > 1 else remaining)
        selected.extend(repeated[:repeat_slots])
        selected.extend(new[:remaining - repeat_slots])
        if len(selected) < limit:
            selected.extend(repeated[repeat_slots:repeat_slots + limit - len(selected)])
    records = []
    errors = []
    for market, entry_gate_reasons in selected:
        ticker = market['ticker']
        try:
            book = (await asyncio.wait_for(kalshi_public.get_orderbook(ticker, depth=20), timeout=12))['orderbook']
            # Record when the book actually arrived, not the scan's start time.
            # A test-supplied clock remains deterministic for fixture diagnostics.
            book_observed = observed if now is not None else datetime.now(timezone.utc)
            event_time = market.get('timing', {}).get('occurrence_datetime')
            try:
                event_dt = datetime.fromisoformat(event_time.replace('Z', '+00:00'))
            except (AttributeError, ValueError, TypeError):
                errors.append({'ticker': ticker, 'error_type': 'EVENT_TIME_UNVERIFIED'})
                continue
            if event_dt.tzinfo is None or event_dt.utcoffset() is None or book_observed >= event_dt:
                errors.append({'ticker': ticker, 'error_type': 'EVENT_ALREADY_STARTED'})
                continue
            sides = {}
            for side in ('YES', 'NO'):
                buy = walk_executable_depth(book, side=side, action='BUY', quantity=quantity)
                sell = walk_executable_depth(book, side=side, action='SELL', quantity=quantity)
                buy_ok = bool(buy.get('fillable'))
                sell_ok = bool(sell.get('fillable'))
                # Same-snapshot executable round-trip is a spread/cost diagnostic,
                # not a forward price forecast or a PAPER trade.
                roundtrip = None
                if buy_ok and sell_ok:
                    buy_price = Decimal(str(buy['vwap_dollars']))
                    sell_price = Decimal(str(sell['vwap_dollars']))
                    entry_fee = Decimal(str(buy['estimated_taker_fee_dollars']))
                    exit_fee = Decimal(str(sell['estimated_taker_fee_dollars']))
                    roundtrip = str((sell_price - buy_price) * quantity - entry_fee - exit_fee)
                sides[side] = {'buy_fillable': buy_ok,
                               'sell_fillable': sell_ok,
                               'instant_roundtrip_net_dollars': roundtrip,
                               'buy_vwap': buy.get('vwap_dollars') if buy_ok else None,
                               'sell_vwap': sell.get('vwap_dollars') if sell_ok else None,
                               'buy_fee': buy.get('estimated_taker_fee_dollars') if buy.get('fillable') else None,
                               'sell_fee': sell.get('estimated_taker_fee_dollars') if sell.get('fillable') else None}
            records.append({'schema': 'kalshi-forward-quote-v1', 'observed_at': book_observed.isoformat(),
                            'ticker': ticker, 'created_time': market['timing']['created_time'],
                            'open_time': market['timing']['open_time'],
                            'occurrence_datetime': market['timing'].get('occurrence_datetime'),
                            'quantity': str(quantity),
                            'entry_gate_reasons': entry_gate_reasons,
                            'entry_gate_passed': not entry_gate_reasons,
                            'sides': sides, 'orders_placed': 0, 'paper_trades_opened': 0})
        except Exception as exc:
            errors.append({'ticker': ticker, 'error_type': type(exc).__name__})
    if records:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8', newline='\n') as output:
            for record in records:
                output.write(json.dumps(record, sort_keys=True) + '\n')
            output.flush()
    return {'status': 'OBSERVATIONS_RECORDED' if records else 'NO_OBSERVABLE_NEW_LISTINGS',
            'observable_new_listings_seen': len(candidates),
            'entry_gate_qualified_new_listings_seen': fully_qualified,
            'pages_scanned': pages_scanned,
            'unique_markets_screened': len(seen), 'records_written': len(records),
            'provider_errors': errors, 'orders_placed': 0, 'paper_trades_opened': 0,
            'unattended_paper_authorized': False}


if __name__ == '__main__':
    print(json.dumps(asyncio.run(collect()), sort_keys=True))