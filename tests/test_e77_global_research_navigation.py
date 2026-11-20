from pathlib import Path

COMMAND=Path("frontend/src/app/page.tsx")
OVERVIEW=Path("frontend/src/app/research/surfaces/page.tsx")
FORWARD=Path("frontend/src/app/research/page.tsx")

def test_e77_command_center_exposes_research_surfaces_navigation():
    text=COMMAND.read_text(encoding="utf-8")
    assert 'SurfaceNavLink' in text
    assert 'href="/research/surfaces"' in text
    assert ">Research Surfaces</SurfaceNavLink>" in text
    assert "This page is watch-only." in text

def test_e77_research_overview_exposes_standard_navigation():
    text=OVERVIEW.read_text(encoding="utf-8")
    assert 'aria-label="Research navigation"' in text
    assert 'href="/research"' in text
    assert ">Forward Evidence</SurfaceNavLink>" in text
    assert 'href="/"' in text
    assert ">Command Center</SurfaceNavLink>" in text

def test_e77_forward_evidence_retains_standard_navigation():
    text=FORWARD.read_text(encoding="utf-8")
    assert 'href="/research/surfaces"' in text
    assert ">Research Surfaces</SurfaceNavLink>" in text
    assert 'href="/"' in text
    assert ">Command Center</SurfaceNavLink>" in text

def test_e77_navigation_change_does_not_add_trading_actions():
    combined="\n".join(p.read_text(encoding="utf-8") for p in (OVERVIEW,FORWARD))
    for token in ("<button", "repair_action", "paperOrder", "brokerOrder", "executeTrade",
                  "strategySelection", "thresholdMutation", "promotionAction"):
        assert token not in combined
    overview=OVERVIEW.read_text(encoding="utf-8")
    assert "Read-only map" in overview
    assert "Trading authority stays gated" in overview
