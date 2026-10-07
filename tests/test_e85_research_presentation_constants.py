from pathlib import Path

PAGE=Path("frontend/src/app/research/surfaces/page.tsx")
PRESENTATION=Path("frontend/src/app/research/surfaces/presentation.ts")

def test_e85_page_consumes_presentation_constants():
    text=PAGE.read_text(encoding="utf-8")
    assert 'import { AUTHORITY_LEGEND, SECTION_POSTURE } from "./presentation";' in text
    assert "AUTHORITY_LEGEND.map" in text
    assert "{SECTION_POSTURE.navigable}" in text
    assert "{SECTION_POSTURE.gated}" in text
    assert "{SECTION_POSTURE.active}" in text

def test_e85_authority_legend_is_typed_read_only_and_frozen():
    text=PRESENTATION.read_text(encoding="utf-8")
    assert "export type AuthorityLegendDefinition = Readonly<{" in text
    assert "readonly AuthorityLegendDefinition[]" in text
    assert text.count("Object.freeze(") >= 5

def test_e85_preserves_authority_legend_visible_contract():
    text=PRESENTATION.read_text(encoding="utf-8")
    for phrase in (
        "Read-only presentation",
        "Information can be viewed and navigated; viewing it grants no trading authority.",
        "Human-review-only evidence",
        "Evidence can inform human review; strategy selection and production promotion remain gated.",
        "Gated capability",
        "Capability remains unavailable pending a separate validated roadmap unlock.",
    ):
        assert phrase in text

def test_e85_preserves_section_posture_visible_contract():
    text=PRESENTATION.read_text(encoding="utf-8")
    for phrase in (
        "Purpose: open established read-only operator and research views. Authority: navigation and observation do not grant trading authority.",
        "Roadmap-confirmed boundaries shown for operator context. These are not destinations or disabled controls. Purpose: show roadmap-confirmed unavailable capabilities for operator context. Authority: gated items are not destinations, controls, or readiness claims.",
        "Genuine evidence accumulation currently in progress. Gated capabilities are listed separately above. Purpose: show genuine evidence accumulation currently in progress. Authority: active evidence does not unlock strategy selection, promotion, PAPER, or execution.",
    ):
        assert phrase in text

def test_e85_presentation_and_page_remain_static_action_free():
    text=PAGE.read_text(encoding="utf-8")+"\n"+PRESENTATION.read_text(encoding="utf-8")
    for token in ("fetch(", "axios", "useEffect", "useState", "<button", "method:\"POST\"", "method:\"PUT\"", "method:\"PATCH\"", "method:\"DELETE\"",
                  "paperOrder", "brokerOrder", "executeTrade", "repair_action"):
        assert token not in text
