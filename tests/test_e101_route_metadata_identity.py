from pathlib import Path

ROOT=Path("frontend/src/app/layout.tsx")
RESEARCH_LAYOUT=Path("frontend/src/app/research/layout.tsx")
SURFACES_LAYOUT=Path("frontend/src/app/research/surfaces/layout.tsx")
RESEARCH_PAGE=Path("frontend/src/app/research/page.tsx")
SURFACES_PAGE=Path("frontend/src/app/research/surfaces/page.tsx")
COMMAND=Path("frontend/src/app/page.tsx")

def test_e101_command_center_has_clear_root_metadata_identity():
    text=ROOT.read_text(encoding="utf-8")
    assert 'title: "Command Center | Project Atlas"' in text
    assert 'description: "Project Atlas operator command center for runtime status and bounded research visibility."' in text

def test_e101_forward_evidence_has_static_route_metadata_outside_client_page():
    layout=RESEARCH_LAYOUT.read_text(encoding="utf-8"); page=RESEARCH_PAGE.read_text(encoding="utf-8")
    assert 'title: "Forward Evidence | Project Atlas"' in layout
    assert "Read-only Project Atlas forward research evidence" in layout
    assert '"use client";' in page
    assert "export const metadata" not in page

def test_e101_research_surfaces_has_distinct_static_route_metadata():
    text=SURFACES_LAYOUT.read_text(encoding="utf-8")
    assert 'title: "Research Surfaces | Project Atlas"' in text
    assert "Read-only map of Project Atlas operator and research surfaces" in text

def test_e101_metadata_layouts_are_pure_passthroughs():
    for path in (RESEARCH_LAYOUT,SURFACES_LAYOUT):
        text=path.read_text(encoding="utf-8")
        assert "return children;" in text
        for token in ('"use client"', "useEffect", "useState", "fetch(", "setInterval", "onClick"):
            assert token not in text

def test_e101_metadata_identity_preserves_runtime_and_authority_boundaries():
    command=COMMAND.read_text(encoding="utf-8"); evidence=RESEARCH_PAGE.read_text(encoding="utf-8"); surfaces=SURFACES_PAGE.read_text(encoding="utf-8")
    assert "/api/live" in command and "}, 8000);" in command
    assert "/api/validation/challengers/research-evidence" in evidence and "setInterval(load,15000)" in evidence
    assert "Automatic real-money execution:" in evidence
    assert "Trading authority stays gated unless a separate validated roadmap execution explicitly unlocks it." in surfaces
