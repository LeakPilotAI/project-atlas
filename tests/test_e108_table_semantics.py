from pathlib import Path

COMMAND=Path("frontend/src/app/page.tsx")
CRYPTO=Path("frontend/src/app/components/CryptoQualityDipsStatusPanel.tsx")
EVIDENCE=Path("frontend/src/app/research/page.tsx")
SURFACES=Path("frontend/src/app/research/surfaces/page.tsx")

def test_e108_all_established_frontend_tables_are_bounded_for_narrow_viewports():
    text=COMMAND.read_text(encoding="utf-8")
    assert text.count("<table") == 3
    assert text.count('<div className="overflow-x-auto">') == 3
    assert 'min-w-[42rem]' in text and 'min-w-[40rem]' in text and 'min-w-[30rem]' in text

def test_e108_all_tables_have_accessible_captions():
    text=COMMAND.read_text(encoding="utf-8")
    assert text.count('<caption className="sr-only">') == 3
    assert "Open paper trades with current entry, mark, stop, excursion, and age data." in text
    assert "Quality dip research candidates with action, price-change context, and thesis." in text
    assert "Stored perpetual opportunities with status, side, and entry price." in text

def test_e108_every_table_header_declares_column_scope():
    text=COMMAND.read_text(encoding="utf-8")
    assert text.count("<th ") == 17
    assert text.count('<th scope="col"') == 17

def test_e108_table_hardening_preserves_visible_data_expressions():
    text=COMMAND.read_text(encoding="utf-8")
    for token in ("fmt(t.entry, 4)","fmt(t.mark, 4)","fmt(t.stop, 4)","fmt(t.mfe_r, 2)","ago(t.opened_at)","fmt(d.pct_from_high, 1)","fmt(d.chg_1d, 1)","fmt(d.chg_5d, 1)","String(d.thesis || \"\")","String(o.status)","String(o.recommendation || \"—\")","fmt(o.entry_price, 4)"):
        assert token in text

def test_e108_table_semantics_preserve_runtime_and_boundary_contracts():
    command=COMMAND.read_text(encoding="utf-8"); crypto=CRYPTO.read_text(encoding="utf-8"); evidence=EVIDENCE.read_text(encoding="utf-8"); surfaces=SURFACES.read_text(encoding="utf-8")
    assert "/api/live" in command and "}, 8000);" in command
    assert 'REFRESH_MS=15000;' in crypto
    assert "/api/validation/challengers/research-evidence" in evidence and "setInterval(load,15000)" in evidence
    assert "Automatic real-money execution:" in evidence
    assert "Trading authority stays gated unless a separate validated roadmap execution explicitly unlocks it." in surfaces
