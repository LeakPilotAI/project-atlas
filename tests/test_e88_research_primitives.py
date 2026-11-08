from pathlib import Path

PAGE=Path("frontend/src/app/research/surfaces/page.tsx")
PRIMITIVES=Path("frontend/src/app/research/surfaces/ResearchPrimitives.tsx")

def test_e88_page_consumes_distinct_research_primitives():
    text=PAGE.read_text(encoding="utf-8")
    assert 'import { ActiveEvidenceState, AuthorityLegendItem } from "./ResearchPrimitives";' in text
    assert "AUTHORITY_LEGEND.map(item=><AuthorityLegendItem" in text
    assert '<ActiveEvidenceState label="E29 forward strategy evidence" value="ACTIVE · genuine evidence only"/>' in text
    assert '<ActiveEvidenceState label="Alpha / cadence / corroboration" value="ACTIVE · strategy selection gated"/>' in text

def test_e88_authority_legend_item_preserves_exact_markup():
    text=PRIMITIVES.read_text(encoding="utf-8")
    legend=text.split("export function AuthorityLegendItem",1)[1].split("export function ActiveEvidenceState",1)[0]
    assert 'className="rounded-lg border border-white/5 p-3"' in legend
    assert '<dt className="font-medium text-zinc-300">{term}</dt>' in legend
    assert '<dd className="mt-1 leading-5 text-zinc-500">{meaning}</dd>' in legend

def test_e88_active_evidence_state_preserves_exact_markup():
    text=PRIMITIVES.read_text(encoding="utf-8")
    state=text.split("export function ActiveEvidenceState",1)[1]
    assert 'className="rounded-lg border border-white/5 px-3 py-3"' in state
    assert '<p className="text-zinc-500">{label}</p>' in state
    assert '<p className="mt-1 text-zinc-300">{value}</p>' in state

def test_e88_primitives_remain_semantically_distinct():
    text=PRIMITIVES.read_text(encoding="utf-8")
    assert "AuthorityLegendItem" in text
    assert "ActiveEvidenceState" in text
    assert "Generic" not in text

def test_e88_primitives_are_pure_static_and_authority_free():
    text=PRIMITIVES.read_text(encoding="utf-8")
    for token in ("use client", "fetch(", "axios", "useEffect", "useState", "<button", "<Link", "href=",
                  'method:"POST"', 'method:"PUT"', 'method:"PATCH"', 'method:"DELETE"',
                  "paperOrder", "brokerOrder", "executeTrade", "repair_action"):
        assert token not in text
