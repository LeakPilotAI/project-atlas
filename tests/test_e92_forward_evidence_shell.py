from pathlib import Path

PAGE=Path("frontend/src/app/research/page.tsx")
SHELL=Path("frontend/src/app/components/ReadOnlyPageShell.tsx")
COMMAND=Path("frontend/src/app/page.tsx")

def test_e92_forward_evidence_adopts_shell_with_preserved_density():
    page=PAGE.read_text(encoding="utf-8")
    shell=SHELL.read_text(encoding="utf-8")
    assert 'import {ReadOnlyPageShell} from "@/app/components/ReadOnlyPageShell";' in page
    assert 'return <ReadOnlyPageShell layout="evidence">' in page
    assert 'evidence:"max-w-6xl mx-auto px-6 py-8 space-y-6"' in shell
    assert 'surfaces:"mx-auto max-w-6xl space-y-5 px-5 py-7 sm:px-6 sm:py-8"' in shell

def test_e92_polling_and_api_contract_are_unchanged():
    text=PAGE.read_text(encoding="utf-8")
    assert 'const API="http://127.0.0.1:8000";' in text
    assert "/api/validation/challengers/research-evidence" in text
    assert "setInterval(load,15000)" in text
    assert "clearInterval(id)" in text
    assert 'setError("Research evidence status unavailable. Atlas remains NOT READY by default.")' in text

def test_e92_evidence_authority_boundaries_remain_visible():
    text=PAGE.read_text(encoding="utf-8")
    for phrase in ("Read-only durable evidence. Research progress is not production approval.","Safety boundary","Live capital:","Automatic promotion:","Automatic real-money execution:","This page exposes research candidates and evidence accumulation only."):
        assert phrase in text

def test_e92_shell_remains_pure_layout_only():
    text=SHELL.read_text(encoding="utf-8")
    for token in ("use client","fetch(","axios","useEffect","useState","<button","<Link","href="):
        assert token not in text

def test_e92_command_center_is_not_migrated():
    assert "ReadOnlyPageShell" not in COMMAND.read_text(encoding="utf-8")
