from pathlib import Path

OVERVIEW=Path("frontend/src/app/research/surfaces/page.tsx")
PRESENTATION=Path("frontend/src/app/research/surfaces/presentation.ts")
CATALOG=Path("frontend/src/app/research/surfaces/catalog.ts")
RESEARCH=Path("frontend/src/app/research/page.tsx")

def test_e76_overview_separates_declared_surfaces():
    text=OVERVIEW.read_text(encoding="utf-8")+"\n"+PRESENTATION.read_text(encoding="utf-8")+"\n"+CATALOG.read_text(encoding="utf-8")
    assert "Research Surfaces" in text
    assert "Alpha / Forward Evidence" in text
    assert "Crypto Quality Dips" in text
    assert "Command Center Operations" in text
    assert 'href:"/research"' in text
    assert 'href:"/"' in text

def test_e76_overview_is_explicitly_read_only_and_gated():
    text=OVERVIEW.read_text(encoding="utf-8")+"\n"+PRESENTATION.read_text(encoding="utf-8")+"\n"+CATALOG.read_text(encoding="utf-8")
    assert "Read-only map" in text
    assert "Human review only · production promotion gated" in text
    assert "Authority locked · no scoring, PAPER, execution, or live capital" in text
    assert "INACTIVE / GATED" in text
    assert "Residual trading Discord lifecycle" in text
    assert "GATED" in text

def test_e76_overview_contains_navigation_not_actions():
    text=OVERVIEW.read_text(encoding="utf-8")+"\n"+PRESENTATION.read_text(encoding="utf-8")+"\n"+CATALOG.read_text(encoding="utf-8")
    assert 'import Link from "next/link"' in text
    assert 'href="/"' in text
    assert "Open read-only surface" in text
    for token in ("fetch(", "axios", "<button", "method:\"POST\"", "method:\"PUT\"", "method:\"PATCH\"", "method:\"DELETE\"",
                  "repair_action", "paperOrder", "brokerOrder", "executeTrade"):
        assert token not in text

def test_e76_existing_forward_evidence_links_to_overview_without_contract_change():
    text=RESEARCH.read_text(encoding="utf-8")
    assert 'href="/research/surfaces"' in text
    assert ">Research Surfaces</Link>" in text
    assert "/api/validation/challengers/research-evidence" in text
    assert "Research progress is not production approval." in text
