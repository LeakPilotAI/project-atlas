from pathlib import Path

COMMAND=Path("frontend/src/app/page.tsx")
CRYPTO=Path("frontend/src/app/components/CryptoQualityDipsStatusPanel.tsx")
EVIDENCE=Path("frontend/src/app/research/page.tsx")
SURFACES=Path("frontend/src/app/research/surfaces/page.tsx")

def test_e107_command_titled_regions_have_accessible_names():
    text=COMMAND.read_text(encoding="utf-8")
    assert 'aria-labelledby="why-no-paper-title"' in text and 'id="why-no-paper-title"' in text
    assert 'aria-labelledby="perp-funnel-title"' in text and 'id="perp-funnel-title"' in text
    assert 'aria-labelledby="active-gates-title"' in text and 'id="active-gates-title"' in text

def test_e107_command_card_exposes_visible_title_as_region_name():
    text=COMMAND.read_text(encoding="utf-8")
    assert 'function Card({ title, children }' in text
    assert '<section aria-label={title} className="rounded-2xl border border-white/8 bg-[#10131a] p-5">' in text
    assert '<h2 className="text-sm font-medium text-zinc-300 mb-3">{title}</h2>' in text

def test_e107_research_section_and_panel_expose_titles_as_region_names():
    text=EVIDENCE.read_text(encoding="utf-8")
    assert 'function Panel' in text and 'return <section aria-label={title} className="rounded-2xl border border-white/8 bg-[#10131a] p-5"><h2' in text
    assert 'function Section' in text and 'return <section aria-label={title} className="rounded-2xl border border-white/8 bg-[#10131a] p-5"><h2' in text

def test_e107_research_repeated_card_is_named_article():
    text=EVIDENCE.read_text(encoding="utf-8")
    assert 'function Card({name,status,children}' in text
    assert 'return <article aria-label={name} className="rounded-xl border border-white/8 bg-black/20 p-4">' in text
    assert '{children}</article>' in text

def test_e107_region_naming_preserves_runtime_and_boundary_contracts():
    command=COMMAND.read_text(encoding="utf-8"); crypto=CRYPTO.read_text(encoding="utf-8"); evidence=EVIDENCE.read_text(encoding="utf-8"); surfaces=SURFACES.read_text(encoding="utf-8")
    assert "/api/live" in command and "}, 8000);" in command
    assert 'REFRESH_MS=15000;' in crypto
    assert "/api/validation/challengers/research-evidence" in evidence and "setInterval(load,15000)" in evidence
    assert "Trading authority stays gated unless a separate validated roadmap execution explicitly unlocks it." in surfaces
