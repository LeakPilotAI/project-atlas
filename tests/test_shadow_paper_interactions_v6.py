from app.services.shadow_paper_interactions import interaction_report


def _row(i,pnl,*,side="LONG",regime="TREND_UP",ext=3.2,q=90):
    return {"trade_id":str(i),"side":side,"regime":regime,"regime_normalized":regime,"net_pnl_r":pnl,"R_multiple":pnl,"features":{"ext_pct":ext,"qscore":q}}


def test_populations_are_never_pooled():
    paper=[_row(i,-1.0) for i in range(40)]
    shadow=[_row(i,1.0) for i in range(40)]
    r=interaction_report(paper=paper,shadow=shadow)
    assert r["paper_n"]==40 and r["shadow_n"]==40
    assert r["combined_performance"] is None
    assert r["populations_pooled"] is False
    assert r["paper_baseline"]["total_r"]==-40.0
    assert r["shadow_baseline"]["total_r"]==40.0


def test_identical_bucket_definitions_expose_delta_only():
    paper=[_row(i,-0.5,ext=3.5,q=90) for i in range(35)]
    shadow=[_row(i,0.5,ext=3.5,q=90) for i in range(35)]
    r=interaction_report(paper=paper,shadow=shadow)
    x=r["interactions"]["trend_ext3_q85"]
    assert x["paper"]["n"]==35 and x["shadow"]["n"]==35
    assert x["comparable_sample"] is True
    assert x["expectancy_delta_shadow_minus_paper"]==1.0
    assert r["automatic_gate_change"] is False


def test_small_samples_cannot_be_comparable_nomination():
    paper=[_row(i,-1.0) for i in range(5)]
    shadow=[_row(i,1.0) for i in range(5)]
    r=interaction_report(paper=paper,shadow=shadow)
    assert r["interactions"]["trend"]["comparable_sample"] is False
    assert r["prospective_nominations"]==[]
    assert r["production_strategy_modified"] is False
    assert r["live_capital_allowed"] is False
