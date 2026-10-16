from pathlib import Path


def test_main_wires_investment_board_router():
    text = Path('backend/app/main.py').read_text(encoding='utf-8')
    assert 'from app.api.investment_board import router as investment_board_router' in text
    assert 'app.include_router(investment_board_router, prefix="/api")' in text


def test_investment_board_attaches_v2_projection_and_keeps_manual_only():
    text = Path('backend/app/api/investment_board.py').read_text(encoding='utf-8')
    assert 'attach_v2_board' in text
    assert 'quality_dips_v2' in text
    assert '"execution": "MANUAL_ONLY"' in text
    assert '"live_capital_allowed": False' in text
    assert '"automatic_real_money_execution": False' in text
    assert '"price_alone_breaks_thesis": False' in text


def test_quality_dips_dashboard_mentions_v2_patient_capital_fields():
    text = Path('backend/app/static/quality_dips.html').read_text(encoding='utf-8')
    assert 'QUALITY DIPS V2' in text
    assert 'patient_state' in text
    assert 'conservative_upside_pct' in text
    assert 'entry_ladder' in text
