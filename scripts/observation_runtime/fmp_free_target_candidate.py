"""FMP free-tier analyst-target candidate assessment. Research only; never grants source authority."""
from __future__ import annotations

from datetime import UTC, datetime
from math import isfinite


def assess_price_target_consensus(payload, *, symbol: str):
    """Reject aggregated price targets as independent originating estimates."""
    if not isinstance(symbol, str) or not symbol.isalpha() or not symbol.isupper():
        raise ValueError('FMP_SYMBOL_REFUSED')
    if not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], dict):
        raise ValueError('FMP_CONSENSUS_SHAPE_REFUSED')
    row = payload[0]
    if row.get('symbol') != symbol:
        raise ValueError('FMP_CONSENSUS_SYMBOL_REFUSED')
    for field in ('targetLow', 'targetConsensus', 'targetHigh', 'targetMedian'):
        value = row.get(field)
        if value is not None and (type(value) not in (float, int) or not isfinite(value) or value <= 0):
            raise ValueError('FMP_CONSENSUS_PRICE_REFUSED')
    return {
        'schema': 'ATLAS_FMP_FREE_TARGET_CANDIDATE_V1',
        'symbol': symbol,
        'provider': 'FINANCIAL_MODELING_PREP',
        'source_kind': 'AGGREGATED_CONSENSUS_NOT_ORIGINATING_ANALYST',
        'individual_analyst_estimates_authenticated': 0,
        'free_endpoint_entitlement_verified': False,
        'operational_source_accepted': False,
        'paper_fill_authorized': False,
        'live_order_authorized': False,
        'reason': 'FMP_INDIVIDUAL_ANALYST_PROVENANCE_AND_FREE_ACCESS_UNVERIFIED',
    }
