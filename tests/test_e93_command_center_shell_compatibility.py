from pathlib import Path

PAGE=Path("frontend/src/app/page.tsx")
SHELL=Path("frontend/src/app/components/ReadOnlyPageShell.tsx")

def test_e93_command_center_intentionally_keeps_its_own_outer_frame():
    text=PAGE.read_text(encoding="utf-8")
    assert "ReadOnlyPageShell" not in text
    assert '<div className="min-h-screen bg-[#07080b] text-zinc-200">' in text
    assert '<header className="border-b border-white/5 bg-[#0b0d12]/90 backdrop-blur sticky top-0 z-10">' in text
    assert '<div className="max-w-7xl mx-auto px-6 py-4 flex flex-wrap items-end justify-between gap-4">' in text
    assert '<main className="max-w-7xl mx-auto px-6 py-6 space-y-6">' in text

def test_e93_command_center_runtime_contract_is_preserved():
    text=PAGE.read_text(encoding="utf-8")
    assert 'const API = "http://127.0.0.1:8000";' in text
    assert '/api/live' in text
    assert "setInterval(() => {" in text
    assert "}, 8000);" in text
    assert "clearInterval(id);" in text
    assert 'setError("API not reachable on port 8000. Keep the Atlas window open.");' in text

def test_e93_command_center_loading_frame_and_panel_placement_are_preserved():
    text=PAGE.read_text(encoding="utf-8")
    assert '<div className="min-h-screen bg-[#07080b] text-zinc-200 flex items-center justify-center">' in text
    assert "Connecting to Atlas" in text
    health=text.index('<section className="flex flex-wrap gap-2">')
    panel=text.index("<CryptoQualityDipsStatusPanel />")
    why=text.index("Why no paper trade")
    assert health < panel < why

def test_e93_watch_only_operator_semantics_remain_visible():
    text=PAGE.read_text(encoding="utf-8")
    assert "Live command center" in text
    assert "Bot runs in the Atlas window. This page is watch-only. Discord is the alert feed." in text
    assert "API down" in text
    assert "API connected" in text

def test_e93_shared_shell_scope_remains_read_only_page_framing():
    text=SHELL.read_text(encoding="utf-8")
    assert '<main className={LAYOUT_CLASS[layout]}>' in text
    assert "max-w-7xl" not in text
    assert "sticky top-0" not in text
    for token in ("use client","fetch(","useEffect","useState","<header","<button"):
        assert token not in text
