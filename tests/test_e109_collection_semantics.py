from pathlib import Path

SURFACES=Path("frontend/src/app/research/surfaces/page.tsx")
COMMAND=Path("frontend/src/app/page.tsx")
CRYPTO=Path("frontend/src/app/components/CryptoQualityDipsStatusPanel.tsx")
EVIDENCE=Path("frontend/src/app/research/page.tsx")

def test_e109_navigable_surfaces_are_an_unordered_collection():
    text=SURFACES.read_text(encoding="utf-8")
    assert '<ul className="grid gap-4 lg:grid-cols-3" aria-label="Atlas research surfaces">' in text
    assert 'RESEARCH_SURFACES.map(surface=><li key={surface.title}><ResearchSurfaceCard surface={surface}/></li>)' in text

def test_e109_gated_capabilities_are_an_unordered_collection():
    text=SURFACES.read_text(encoding="utf-8")
    assert '<ul className="grid gap-3 md:grid-cols-2">' in text
    assert 'GATED_CAPABILITIES.map(capability=><li key={capability.title}><GatedCapabilityCard capability={capability}/></li>)' in text

def test_e109_active_evidence_states_are_list_items():
    text=SURFACES.read_text(encoding="utf-8")
    assert '<ul className="mt-3 grid gap-2 text-xs md:grid-cols-2">' in text
    assert '<li><ActiveEvidenceState label="E29 forward strategy evidence" value="ACTIVE · genuine evidence only"/></li>' in text
    assert '<li><ActiveEvidenceState label="Alpha / cadence / corroboration" value="ACTIVE · strategy selection gated"/></li>' in text

def test_e109_authority_legend_remains_definition_list_not_generic_list():
    text=SURFACES.read_text(encoding="utf-8")
    assert '<dl className="mt-3 grid gap-3 text-xs md:grid-cols-3">' in text
    assert 'AUTHORITY_LEGEND.map(item=><AuthorityLegendItem' in text

def test_e109_collection_semantics_preserve_runtime_and_boundary_contracts():
    command=COMMAND.read_text(encoding="utf-8"); crypto=CRYPTO.read_text(encoding="utf-8"); evidence=EVIDENCE.read_text(encoding="utf-8"); surfaces=SURFACES.read_text(encoding="utf-8")
    assert "/api/live" in command and "}, 8000);" in command
    assert 'REFRESH_MS=15000;' in crypto
    assert "/api/validation/challengers/research-evidence" in evidence and "setInterval(load,15000)" in evidence
    assert "Automatic real-money execution:" in evidence
    assert "Trading authority stays gated unless a separate validated roadmap execution explicitly unlocks it." in surfaces
