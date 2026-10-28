"""Bounded explicit-input reuse of the existing Quality Dips research board.

No scanner/bootstrap, history/cache reads, publication, notifications or financial
writes. This is calculation, NOT source authentication or executable-price proof.
The existing source-publication authority must verify input provenance and current
instrument/calendar/quote evidence before this result can support a command.
"""
from app.investment.board import build_quality_dips_board
from app.investment.quality_dips_v2_board import build_v2_projection
from app.services.paper_financial_replay import body, strict


def project_explicit_research(rows):
    if type(rows) is not list or not 0 < len(rows) <= 50:
        raise ValueError('QD_EXPLICIT_BOUNDED_RESEARCH_REQUIRED')
    # Strict JSON also rejects nonfinite financial/research numbers. Copy before
    # invoking legacy pure calculations so source evidence remains unchanged.
    encoded = body(rows)
    if len(encoded.encode()) > 131072:
        raise ValueError('QD_EXPLICIT_RESEARCH_CAPACITY')
    copied = strict(encoded)
    symbols = []
    for row in copied:
        if (type(row) is not dict or type(row.get('symbol')) is not str
                or not row['symbol'] or row['symbol'] != row['symbol'].strip().upper()
                or row.get('asset_type') not in ('STOCK', 'ETF', 'SECTOR_ETF')):
            raise ValueError('QD_EXPLICIT_RESEARCH_INSTRUMENT')
        symbols.append(row['symbol'])
    if len(set(symbols)) != len(symbols):
        raise ValueError('QD_AMBIGUOUS_RESEARCH_REVISION')
    indexed = {row['symbol']: row for row in copied}
    board = build_quality_dips_board(copied, (), limit=50)
    for item in board:
        item['quality_dips_v2'] = build_v2_projection(
            indexed[item['symbol']], allow_stored_evidence=False)
    return board
