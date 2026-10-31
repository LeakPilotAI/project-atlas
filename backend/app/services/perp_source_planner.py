"""Existing discovery/limit/static-exit policies -> admitted PAPER control/events.

Source.read_cut is an accepted cache reader, never an implicit provider refresh.
Book/rate observations are not authority; injected source/fee/session verifiers
must authenticate them. Maker queue evidence is separate from discovery/marks.
"""
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import ROUND_FLOOR, localcontext

from app.services.paper_financial_replay import (
    FinancialSourceUncertain,
    body,
    digest,
    number,
    strict,
    text,
)
from app.services.perp_resting_writer import RestingPerpWriter
from app.trading_core.models import Side
from app.trading_core.perp_board import build_perp_board
from app.trading_core.perp_discovery import analyze_candles, rank_setup, shortlist_markets
from app.trading_core.perp_manual_planner import build_manual_perp_plan
from app.trading_core.perp_setup_lifecycle import reconcile_setups
from app.trading_core.perp_setup_state import classify_setup_state


def discovery_plans(markets, candles, symbols):
    """Same pure discovery and research ladder functions used by native service."""
    output = []
    if type(markets) is not list or len(markets) > 32 or len({r['symbol'] for r in markets}) != len(markets):
        raise ValueError('BOUNDED_UNAMBIGUOUS_PERP_DISCOVERY_REQUIRED')
    for row in shortlist_markets(markets, limit=8):
        if row['symbol'] not in symbols:
            continue
        for key in ('price', 'volume_24h', 'open_interest', 'funding_rate'):
            number(str(row[key]))
        bars = candles.get(row['symbol'])
        if type(bars) is not list or len(bars) > 96:
            raise ValueError('PERP_CANDLE_SOURCE_MISSING_OR_UNBOUNDED')
        for bar in bars:
            if number(str(bar['close'])) <= 0:
                raise ValueError('PERP_CANDLE_PRICE_INVALID')
        ranked = rank_setup(symbol=row['symbol'], price=float(row['price']), volume_24h=float(row['volume_24h']),
                            open_interest=float(row['open_interest']), funding_rate=float(row['funding_rate']),
                            structure=analyze_candles(bars))
        if ranked is None:
            continue
        plan = build_manual_perp_plan(symbol=ranked.symbol, side=ranked.side, reference_price=ranked.price,
            hyperliquid_symbols=symbols, volatility_pct=max(.15, ranked.volatility_pct), target_rr=1.8, secondary_rr=3)
        fields = {key: getattr(plan, key) for key in ('l1', 'l2', 'l3', 'stop', 'tp1', 'tp2')}
        state = classify_setup_state(side=ranked.side, mark=ranked.price, **fields)
        output.append({**asdict(ranked), 'side': ranked.side.value, 'state': state.state.value,
                       'levels': fields, 'source_plan': {**asdict(plan), 'side': plan.side.value}})
    output.sort(key=lambda row: row['score'], reverse=True)
    return output[:8]


class PerpSourcePlanner:
    def __init__(self, *, writer, source, clock, session_id):
        if type(writer) is not RestingPerpWriter or source is None or clock is None or not session_id:
            raise ValueError('PERP_EXISTING_WRITER_AND_ACCEPTED_SOURCE_REQUIRED')
        self.writer, self.source, self.clock, self.session_id = writer, source, clock, session_id
        self.components = {'writer': writer, 'source': source, 'clock': clock, 'session_id': session_id}
        self.last = None
        self._last_source = None
        self._verify()

    def _verify(self):
        verifier = getattr(self.writer.authority, 'verify_planner_components', None)
        if (any(getattr(self, key) is not self.components[key] for key in ('writer', 'source', 'clock'))
                or self.session_id != self.components['session_id']
                or verifier is None or verifier(self.writer.binding, self.components) is not True):
            raise ValueError('PERP_PLANNER_COMPONENT_AUTHORITY_REQUIRED')

    def _source(self, observation, cut):
        self._verify()
        packet = strict(body(self.source.read_cut()))
        if (set(packet) != {'schema', 'source_id', 'revision', 'observed_at', 'markets', 'candles', 'books',
                           'funding', 'oracles', 'maker_fills', 'setups'} or packet['schema'] != 'PERP_STRATEGY_SOURCE_V1'
                or type(packet['revision']) is not int or packet['revision'] < 1
                or type(packet['observed_at']) is not int or not 0 <= self.clock() - packet['observed_at'] <= 5
                or len(body(packet).encode()) > 131072 or body(self.writer._cut()) != body(cut)):
            raise ValueError('PERP_CURRENT_SOURCE_REVISION_REQUIRED')
        verifier = getattr(self.writer.authority, 'verify_strategy_source', None)
        if verifier is None or verifier(self.writer.binding, packet, observation, cut, self.writer._control()) is not True:
            raise ValueError('PERP_STRATEGY_SOURCE_AUTHENTICATION_REQUIRED')
        text(packet['source_id'])
        identity = (packet['source_id'], packet['revision'], digest(packet))
        if self._last_source is not None and (identity[0] != self._last_source[0] or identity[1] < self._last_source[1]
                or identity[1] == self._last_source[1] and identity[2] != self._last_source[2]):
            raise ValueError('PERP_SOURCE_ROLLBACK_OR_CONFLICT')
        self._last_source = identity
        return packet

    def _book(self, packet, symbol):
        raw = packet['books'].get(symbol)
        if (type(raw) is not dict or raw.get('schema') != 'ATLAS_HYPERLIQUID_PUBLIC_BOOK_V1'
                or raw.get('symbol') != symbol or type(raw.get('book_timestamp_ms')) is not int
                or not 0 <= self.clock() * 1000 - raw['book_timestamp_ms'] <= 5000):
            raise ValueError('PERP_EXECUTABLE_SOURCE_BOOK_REQUIRED')
        policy = self.writer.manifest['perp_policy']
        verifier = getattr(self.writer.authority, 'verify_execution_source', None)
        if verifier is None or verifier(self.writer.binding, packet, raw, policy) is not True:
            raise ValueError('PERP_INSTRUMENT_AND_MODELED_FEE_ACCEPTANCE_REQUIRED')
        return {'source': policy['market_source'], 'instrument_cut': policy['instrument_cut'], 'symbol': symbol,
                'observed_at': raw['book_timestamp_ms'] // 1000, 'sequence': digest(raw),
                **{k: raw[k] for k in ('bid', 'ask', 'bid_size', 'ask_size', 'mark')},
                'fee_schedule_id': policy['fee_schedule_id']}

    def _proposal(self, command, cut, packet):
        proposal = {'operation_id': command['operation_id'], 'kind': command['kind'], 'command': command,
                    'source_head': cut['head'], 'strategy_ref': 'SOURCE:' + digest([packet['source_id'], packet['revision'], packet])}
        self.writer.preview(proposal, None)
        return proposal

    async def next_proposal(self, observation, cut):
        packet = self._source(observation, cut)
        control = self.writer._control()['state']['orders']
        if any(row['state'] == 'FILL_PENDING' for row in control.values()):
            raise FinancialSourceUncertain('PERP_PENDING_FINANCIAL_EFFECT_UNKNOWN')
        now, manifest = self.clock(), self.writer.manifest
        for key, position in sorted(cut['state']['positions'].items()):
            if number(position['remaining']) <= 0:
                continue
            base = {'schema': 'PAPER_PERP_COMMAND_V2', 'epoch': manifest['epoch'], 'timestamp': now,
                    'expected_source_revision': cut['state']['revision'], 'position_id': key,
                    'expected_position_revision': position['revision']}
            if position['next_funding'] <= now:
                symbol, at = position['symbol'], position['next_funding']
                history, oracle = packet['funding'].get(symbol), packet['oracles'].get(f'{symbol}:{at}')
                verifier = getattr(self.writer.authority, 'verify_settlement_source', None)
                if (history is None or oracle is None or history.get('schema') != 'ATLAS_HYPERLIQUID_FUNDING_HISTORY_V1'
                        or history.get('rate_history_complete') is not True or history.get('symbol') != symbol
                        or oracle.get('symbol') != symbol or oracle.get('settlement_at') != at
                        or verifier is None or verifier(self.writer.binding, history, oracle, now) is not True):
                    raise ValueError('PERP_SETTLEMENT_RATE_AND_HISTORICAL_ORACLE_REQUIRED')
                records = [r for r in history['records'] if r['settlement_at_ms'] == at * 1000]
                if len(records) != 1 or now > at + 30 or number(oracle['price']) <= 0:
                    raise ValueError('PERP_SETTLEMENT_MISSING_OR_SEPARATE_RECOVERY_REQUIRED')
                evidence = {'source': manifest['perp_policy']['funding_source'], 'symbol': symbol, 'settlement_at': at,
                            'interval_seconds': 3600, 'rate': records[0]['hourly_rate'], 'oracle': oracle['price'],
                            'source_id': digest([history, oracle])}
                return self._proposal({**base, 'kind': 'FUNDING', 'operation_id': 'funding:' + digest([manifest['epoch'], key, at]),
                                       'evidence': evidence}, cut, packet)
            book = self._book(packet, position['symbol'])
            origin = control.get(position['origin_ref'])
            if origin is None or origin['state'] != 'ACKNOWLEDGED':
                raise ValueError('PERP_ORIGINAL_ACKNOWLEDGED_ORDER_REQUIRED')
            plan = origin['order']['plan']
            executable = book['bid'] if position['side'] == 'LONG' else book['ask']
            state = classify_setup_state(side=Side(position['side']), mark=float(executable), entered=True,
                **{k: float(plan[k]) for k in ('l1', 'l2', 'l3', 'stop', 'tp1', 'tp2')})
            if state.state.value in ('INVALIDATED', 'TP1_HIT', 'TP2_HIT'):
                return self._proposal({**base, 'kind': 'EXIT', 'operation_id': 'exit:' + digest([key, position['revision'], state.state.value]),
                                       'quantity': position['remaining'], 'liquidity': 'TAKER', 'evidence': book}, cut, packet)
            if number(book['mark']) != number(position['mark']) or book['observed_at'] > position['mark_at']:
                evidence = {k: book[k] for k in ('source', 'instrument_cut', 'symbol', 'observed_at', 'mark')}
                evidence['source_id'] = book['sequence']
                return self._proposal({**base, 'kind': 'MARK', 'operation_id': 'mark:' + digest([key, book]), 'evidence': evidence}, cut, packet)
        for key, row in sorted(control.items()):
            if row['state'] != 'RESERVED':
                continue
            order = row['order']
            if order['session_id'] != self.session_id:
                raise ValueError('PERP_OLD_SESSION_RESTING_ORDER_REFUSED')
            if now >= order['expires_at']:
                return {'operation_id': 'cancel:' + key, 'kind': 'CANCEL_RESTING_ORDER', 'order': order}
            proof = packet['maker_fills'].get(key)
            if proof is None:
                continue  # Mark touch/resting label is never a fill.
            book = self._book(packet, order['symbol'])
            book['maker_execution'] = proof
            command = {'schema': 'PAPER_PERP_MAKER_FILL_V1', 'epoch': manifest['epoch'], 'kind': 'ENTRY',
                'operation_id': 'maker:' + digest([manifest['epoch'], key]), 'expected_source_revision': cut['state']['revision'],
                'timestamp': now, 'symbol': order['symbol'], 'side': order['side'], 'quantity': proof['filled_quantity'],
                'leverage': order['leverage'], 'risk_price': order['risk_price'], 'origin_ref': key,
                'liquidity': 'MAKER', 'evidence': book}
            return self._proposal(command, cut, packet)
        if any(row['state'] == 'RESERVED' for row in control.values()):
            self.last = 'RESTING_NO_EXECUTION_EVIDENCE'
            return None
        plans = discovery_plans(packet['markets'], packet['candles'], manifest['perp_policy']['symbols'])
        previous = {row['order']['plan']['discovery']['setup_key']: row['order']['plan']['discovery']
                    for row in control.values() if 'discovery' in row['order']['plan']}
        if type(packet['setups']) is not list or len(packet['setups']) > 32:
            raise ValueError('PERP_AUTHENTICATED_LIFECYCLE_SNAPSHOT_REQUIRED')
        if len({row['setup_key'] for row in packet['setups']}) != len(packet['setups']):
            raise ValueError('PERP_CONFLICTING_LIFECYCLE_SNAPSHOT')
        previous.update({row['setup_key']: row for row in packet['setups']})
        plans = reconcile_setups(plans, previous=previous.values(), now=datetime.fromtimestamp(now, UTC))
        for row in build_perp_board(plans):
            if row['manual_instruction']['action'] != 'PLACE_RESTING_L1':
                continue
            source = next(p for p in plans if p['symbol'] == row['symbol'] and p['side'] == row['side'])
            plan = source['source_plan']
            book = self._book(packet, row['symbol'])
            limit, stop = number(str(plan['l1'])), number(str(plan['stop']))
            risk = abs(limit - stop)
            raw = packet['books'][row['symbol']]
            if type(raw.get('size_decimals')) is not int or not 0 <= raw['size_decimals'] <= 8:
                raise ValueError('PERP_AUTHENTICATED_QUANTITY_PRECISION_REQUIRED')
            step = number('1') / (number('10') ** raw['size_decimals'])
            plan = {**plan, **source['levels'], 'quantity_step': str(step), 'execution_policy': 'STATIC_SETUP_TP1_V1',
                    'discovery': {k: v for k, v in source.items() if k != 'source_plan'}}
            limit, stop = number(str(plan['l1'])), number(str(plan['stop']))
            risk = abs(limit - stop)
            policy = manifest['perp_policy']
            with localcontext() as context:
                context.prec = 28
                qty = min(number(policy['risk_limit']) / risk, number(policy['max_notional']) / limit)
                qty = (qty / step).to_integral_value(rounding=ROUND_FLOOR) * step
            if qty <= 0:
                continue
            ident = 'resting:' + digest([manifest['epoch'], self.session_id, packet['source_id'], source['setup_key'],
                                         source['first_seen_at'], source['paper_mirror_epoch_at']])
            if ident in control:
                continue
            order = {'schema': 'PERP_RESTING_ORDER_V1', 'epoch': manifest['epoch'], 'order_id': ident,
                'session_id': self.session_id, 'symbol': row['symbol'], 'side': row['side'], 'quantity': str(qty),
                'limit_price': str(limit), 'stop_price': str(stop), 'risk_price': str(risk),
                'leverage': str(min(number('1'), number(policy['max_leverage']))),
                'created_at': now, 'expires_at': now + 21600, 'source_id': packet['source_id'],
                'source_revision': packet['revision'], 'source_digest': digest(packet), 'plan': plan}
            proposal = {'operation_id': 'arm:' + ident, 'kind': 'RESTING_ORDER', 'order': order}
            self.writer.verify_resting(proposal, observation)
            return proposal
        self.last = 'NO_ACTIONABLE_SETUP'
        return None
