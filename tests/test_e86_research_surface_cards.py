from pathlib import Path

PAGE=Path("frontend/src/app/research/surfaces/page.tsx")
CARDS=Path("frontend/src/app/research/surfaces/SurfaceCards.tsx")
CATALOG=Path("frontend/src/app/research/surfaces/catalog.ts")

def test_e86_page_uses_pure_card_components():
    text=PAGE.read_text(encoding="utf-8")
    assert 'import { GatedCapabilityCard, ResearchSurfaceCard } from "./SurfaceCards";' in text
    assert "RESEARCH_SURFACES.map(surface=><ResearchSurfaceCard" in text
    assert "GATED_CAPABILITIES.map(capability=><GatedCapabilityCard" in text

def test_e86_navigable_card_preserves_link_and_postures():
    text=CARDS.read_text(encoding="utf-8")
    assert "export function ResearchSurfaceCard" in text
    assert '<SurfaceStatusBadge status={surface.status}/>' in text
    assert '<Posture label="Purpose" value={surface.purpose}/>' in text
    assert '<Posture label="Data posture" value={surface.dataPosture}/>' in text
    assert '<Posture label="Authority posture" value={surface.authorityPosture}/>' in text
    assert '<Link href={surface.href}' in text
    assert "Open read-only surface →" in text

def test_e86_gated_card_is_non_clickable_and_gated():
    text=CARDS.read_text(encoding="utf-8")
    gated=text.split("export function GatedCapabilityCard",1)[1].split("function Posture",1)[0]
    assert '<SurfaceStatusBadge status="GATED"/>' in gated
    assert "capability.title" in gated and "capability.detail" in gated
    assert "<Link" not in gated
    assert "href=" not in gated
    assert "<button" not in gated

def test_e86_card_components_preserve_css_contracts():
    text=CARDS.read_text(encoding="utf-8")
    assert 'className="flex min-h-64 flex-col rounded-2xl border border-white/8 bg-[#10131a] p-5"' in text
    assert 'className="rounded-2xl border border-white/8 bg-[#0c0e13] p-4"' in text
    assert 'className="mt-auto pt-5 text-xs font-medium text-cyan-300"' in text

def test_e86_components_remain_pure_static_and_authority_free():
    text=CARDS.read_text(encoding="utf-8")
    for token in ("use client", "fetch(", "axios", "useEffect", "useState", "<button",
                  'method:"POST"', 'method:"PUT"', 'method:"PATCH"', 'method:"DELETE"',
                  "paperOrder", "brokerOrder", "executeTrade", "repair_action"):
        assert token not in text

def test_e86_catalog_remains_canonical_content_source():
    cards=CARDS.read_text(encoding="utf-8")
    catalog=CATALOG.read_text(encoding="utf-8")
    assert 'import type { GatedCapabilityDefinition, ResearchSurfaceDefinition } from "./catalog";' in cards
    assert "Alpha / Forward Evidence" in catalog
    assert "Crypto Quality Dips autonomy" in catalog
    assert "Alpha / Forward Evidence" not in cards
    assert "Crypto Quality Dips autonomy" not in cards
