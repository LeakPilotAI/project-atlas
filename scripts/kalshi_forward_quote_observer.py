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
    payload = await asyncio.wait_for(kalshi_public.get_markets(status='open', limit=40), timeout=12)
    candidates = [m for m in payload.get('markets', []) if not scanner._prefilter_reasons(m, observed)]
    records = []
    errors = []
    for market in candidates[:limit]:
        ticker = market['ticker']
        try:
            book = (await asyncio.wait_for(kalshi_public.get_orderbook(ticker, depth=20), timeout=12))['orderbook']
            sides = {}
            for side in ('YES', 'NO'):
                buy = walk_executable_depth(book, side=side, action='BUY', quantity=quantity)
                sell = walk_executable_depth(book, side=side, action='SELL', quantity=quantity)
                sides[side] = {'buy_fillable': bool(buy.get('fillable')),
                               'buy_vwap': buy.get('vwap_dollars') if buy.get('fillable') else None,
                               'sell_fillable': bool(sell.get('fillable')),
                               'sell_vwap': sell.get('vwap_dollars') if sell.get('fillable') else None,
                               'buy_fee': buy.get('estimated_taker_fee_dollars') if buy.get('fillable') else None,
                               'sell_fee': sell.get('estimated_taker_fee_dollars') if sell.get('fillable') else None}
            records.append({'schema': 'kalshi-forward-quote-v1', 'observed_at': observed.isoformat(),
                            'ticker': ticker, 'created_time': market['timing']['created_time'],
                            'open_time': market['timing']['open_time'], 'quantity': str(quantity),
                            'sides': sides, 'orders_placed': 0, 'paper_trades_opened': 0})
        except Exception as exc:
            errors.append({'ticker': ticker, 'error_type': type(exc).__name__})
    if records:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8', newline='\n') as output:
            for record in records:
                output.write(json.dumps(record, sort_keys=True) + '\n')
            output.flush()
    return {'status': 'OBSERVATIONS_RECORDED' if records else 'NO_ELIGIBLE_NEW_LISTINGS',
            'eligible_new_listings_seen': len(candidates), 'records_written': len(records),
            'provider_errors': errors, 'orders_placed': 0, 'paper_trades_opened': 0,
            'unattended_paper_authorized': False}


if __name__ == '__main__':
    print(json.dumps(asyncio.run(collect()), sort_keys=True))