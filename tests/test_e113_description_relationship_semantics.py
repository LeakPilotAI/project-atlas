from pathlib import Path

CARDS=Path("frontend/src/app/research/surfaces/SurfaceCards.tsx")
CRYPTO=Path("frontend/src/app/components/CryptoQualityDipsStatusPanel.tsx")
COMMAND=Path("frontend/src/app/page.tsx")
EVIDENCE=Path("frontend/src/app/research/page.tsx")
SURFACES=Path("frontend/src/app/research/surfaces/page.tsx")

def test_e113_research_surface_article_owns_existing_detail_description():
    text=CARDS.read_text(encoding="utf-8")
    assert 'const detailId=`${headingId}-detail`;' in text
    assert '<article aria-labelledby={headingId} aria-describedby={detailId}' in text
    assert '<p id={detailId} className="mt-3 text-sm leading-6 text-zinc-400">{surface.detail}</p>' in text

def test_e113_gated_capability_article_owns_existing_detail_description():
    text=CARDS.read_text(encoding="utf-8")
    assert text.count('const detailId=`${headingId}-detail`;') == 2
    assert '<p id={detailId} className="mt-2 text-xs leading-5 text-zinc-500">{capability.detail}</p>' in text

def test_e113_crypto_section_owns_existing_boundary_description():
    text=CRYPTO.read_text(encoding="utf-8")
    assert 'aria-labelledby="crypto-quality-dips-title" aria-describedby="crypto-quality-dips-boundary"' in text
    assert 'id="crypto-quality-dips-boundary"' in text
    assert "Read-only evidence surface. No scoring, PAPER, execution, repair, or live-capital authority." in text

def test_e113_description_hardening_preserves_visible_card_content():
    text=CARDS.read_text(encoding="utf-8")
    assert "{surface.title}" in text and "{surface.detail}" in text
    assert "{capability.title}" in text and "{capability.detail}" in text
    assert "Open read-only surface →" in text

def test_e113_runtime_and_authority_contracts_preserved():
    command=COMMAND.read_text(encoding="utf-8")
    crypto=CRYPTO.read_text(encoding="utf-8")
    evidence=EVIDENCE.read_text(encoding="utf-8")
    surfaces=SURFACES.read_text(encoding="utf-8")
    assert "/api/live" in command and "}, 8000);" in command
    assert "REFRESH_MS=15000;" in crypto
    assert "/api/validation/challengers/research-evidence" in evidence and "setInterval(load,15000)" in evidence
    assert "Automatic real-money execution:" in evidence
    assert "Trading authority stays gated unless a separate validated roadmap execution explicitly unlocks it." in surfaces
