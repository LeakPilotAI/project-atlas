from pathlib import Path

COMMAND=Path("frontend/src/app/page.tsx")
EVIDENCE=Path("frontend/src/app/research/page.tsx")
SURFACES=Path("frontend/src/app/research/surfaces/page.tsx")
IDENTITY=Path("frontend/src/app/components/PageIdentity.tsx")


def test_e97_command_center_exposes_navigation_and_live_status_semantics():
    text=COMMAND.read_text(encoding="utf-8")
    assert '<nav aria-label="Research navigation"><SurfaceNavLink href="/research/surfaces" variant="primary">Research Surfaces</SurfaceNavLink></nav>' in text
    assert 'role="status" aria-live="polite"' in text
    assert 'role="alert" className="rounded-xl border border-rose-500/30' in text
    assert '<header className="border-b border-white/5 bg-[#0b0d12]/90 backdrop-blur sticky top-0 z-10">' in text
    assert '<main id="main-content" tabIndex={-1} className="max-w-7xl mx-auto px-6 py-6 space-y-6">' in text


def test_e97_forward_evidence_identity_navigation_row_is_a_header_landmark():
    text=EVIDENCE.read_text(encoding="utf-8")
    assert '<ReadOnlyPageShell layout="evidence"><header className="flex flex-wrap items-start justify-between gap-4"><PageIdentity' in text
    assert '<nav className="flex flex-wrap gap-2" aria-label="Research navigation">' in text
    assert '</SurfaceNavLink></nav></header>{error&&<div role="alert"' in text
    assert 'title="Forward Evidence Panel"' in text


def test_e97_research_surfaces_existing_landmarks_and_heading_links_remain_intact():
    text=SURFACES.read_text(encoding="utf-8")
    assert '<header className="flex flex-wrap items-start justify-between gap-4">' in text
    assert '<nav className="flex flex-wrap gap-2" aria-label="Research navigation">' in text
    for target in (
        'aria-labelledby="research-boundary-title"',
        'aria-labelledby="authority-legend-title"',
        'aria-labelledby="navigable-surfaces-title"',
        'aria-labelledby="gated-capabilities-title"',
        'aria-labelledby="active-evidence-title"',
    ):
        assert target in text


def test_e97_page_identity_remains_the_single_shared_h1_owner():
    identity=IDENTITY.read_text(encoding="utf-8")
    assert '<h1 className="mt-1 text-2xl font-semibold tracking-tight text-white">{title}</h1>' in identity
    for path in (COMMAND,EVIDENCE,SURFACES):
        text=path.read_text(encoding="utf-8")
        assert "<PageIdentity" in text
        assert "<h1" not in text


def test_e97_semantic_polish_preserves_runtime_and_authority_boundaries():
    command=COMMAND.read_text(encoding="utf-8")
    evidence=EVIDENCE.read_text(encoding="utf-8")
    surfaces=SURFACES.read_text(encoding="utf-8")
    assert "/api/live" in command and "}, 8000);" in command and "<CryptoQualityDipsStatusPanel />" in command
    assert "/api/validation/challengers/research-evidence" in evidence
    assert "setInterval(load,15000)" in evidence and "clearInterval(id)" in evidence
    assert "Live capital:" in evidence and "Automatic real-money execution:" in evidence
    assert "Trading authority stays gated unless a separate validated roadmap execution explicitly unlocks it." in surfaces
    assert "fetch(" not in surfaces and "useEffect" not in surfaces and "useState" not in surfaces
