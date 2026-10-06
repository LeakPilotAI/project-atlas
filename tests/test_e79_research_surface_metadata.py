from pathlib import Path

OVERVIEW=Path("frontend/src/app/research/surfaces/page.tsx")

def test_e79_cards_define_bounded_static_metadata():
    text=OVERVIEW.read_text(encoding="utf-8")
    assert 'purpose:string;dataPosture:string;authorityPosture:string' in text
    assert '<Posture label="Purpose" value={surface.purpose}/>' in text
    assert '<Posture label="Data posture" value={surface.dataPosture}/>' in text
    assert '<Posture label="Authority posture" value={surface.authorityPosture}/>' in text
    assert "<dl" in text and "<dt" in text and "<dd" in text

def test_e79_alpha_metadata_preserves_evidence_boundary():
    text=OVERVIEW.read_text(encoding="utf-8")
    assert "Evaluate genuine forward challenger evidence for human review." in text
    assert "Prospective evidence · accumulated over time · no synthetic acceleration." in text
    assert "production promotion gated · strategy selection remains gated" in text

def test_e79_crypto_metadata_preserves_public_contract_boundary():
    text=OVERVIEW.read_text(encoding="utf-8")
    assert "Present bounded Crypto Quality Dips evidence readiness and integrity context." in text
    assert "Frozen public read-only contract · fail-closed consumer · no store internals." in text
    assert "no scoring, PAPER, execution, or live capital · repair authority unavailable" in text

def test_e79_command_center_metadata_preserves_watch_only_boundary():
    text=OVERVIEW.read_text(encoding="utf-8")
    assert "Provide operator visibility into Atlas runtime and bounded research status." in text
    assert "existing runtime feeds only · no authority inferred from display" in text
    assert "Watch-only visibility · navigation and observation do not grant trading authority." in text

def test_e79_overview_stays_static_and_action_free():
    text=OVERVIEW.read_text(encoding="utf-8")
    for token in ("fetch(", "axios", "useEffect", "useState", "<button", "POST", "PUT", "PATCH", "DELETE",
                  "paperOrder", "brokerOrder", "executeTrade", "repair_action"):
        assert token not in text
