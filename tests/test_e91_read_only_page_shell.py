from pathlib import Path

PAGE=Path("frontend/src/app/research/surfaces/page.tsx")
SHELL=Path("frontend/src/app/components/ReadOnlyPageShell.tsx")

def test_e91_shell_preserves_e90_outer_presentation_contract():
    text=SHELL.read_text(encoding="utf-8")
    assert 'className="min-h-screen bg-[#07080b] text-zinc-200"' in text
    assert 'className="mx-auto max-w-6xl space-y-5 px-5 py-7 sm:px-6 sm:py-8"' in text
    assert "{children}" in text

def test_e91_shell_is_pure_read_only_and_runtime_free():
    text=SHELL.read_text(encoding="utf-8")
    assert 'import type { ReactNode } from "react";' in text
    for token in ("use client", "fetch(", "axios", "useEffect", "useState", "<button", "<Link", "href=",
                  'method:"POST"', 'method:"PUT"', 'method:"PATCH"', 'method:"DELETE"',
                  "paperOrder", "brokerOrder", "executeTrade", "repair_action"):
        assert token not in text

def test_e91_research_surfaces_adopts_shell_only():
    text=PAGE.read_text(encoding="utf-8")
    assert 'import { ReadOnlyPageShell } from "@/app/components/ReadOnlyPageShell";' in text
    assert "return <ReadOnlyPageShell>" in text
    assert "</ReadOnlyPageShell>" in text
    assert 'min-h-screen bg-[#07080b] text-zinc-200' not in text
    assert 'mx-auto max-w-6xl space-y-5 px-5 py-7 sm:px-6 sm:py-8' not in text

def test_e91_e89_composition_order_survives_shell_adoption():
    text=PAGE.read_text(encoding="utf-8")
    markers=["<header",'aria-labelledby="research-boundary-title"','aria-labelledby="authority-legend-title"',
             'aria-labelledby="navigable-surfaces-title"','aria-labelledby="gated-capabilities-title"',
             'aria-labelledby="active-evidence-title"']
    positions=[text.index(marker) for marker in markers]
    assert positions == sorted(positions)

def test_e91_routes_accessibility_and_gates_remain_present():
    text=PAGE.read_text(encoding="utf-8")
    assert '<Link href="/research"' in text
    assert '<Link href="/"' in text
    for id_ in ("research-boundary-title","authority-legend-title","navigable-surfaces-title","gated-capabilities-title","active-evidence-title"):
        assert f'aria-labelledby="{id_}"' in text
