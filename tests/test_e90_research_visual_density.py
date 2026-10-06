from pathlib import Path

PAGE=Path("frontend/src/app/research/surfaces/page.tsx")
CARDS=Path("frontend/src/app/research/surfaces/SurfaceCards.tsx")
SHELL=Path("frontend/src/app/components/ReadOnlyPageShell.tsx")

def test_e90_bounded_density_classes_are_present():
    page=PAGE.read_text(encoding="utf-8")
    cards=CARDS.read_text(encoding="utf-8")
    shell=SHELL.read_text(encoding="utf-8")
    assert 'space-y-5 px-5 py-7 sm:px-6 sm:py-8' in shell
    assert 'bg-amber-500/5 p-4 sm:p-5' in page
    assert page.count('bg-[#10131a] p-4 sm:p-5') >= 2
    assert 'min-h-60 flex-col rounded-2xl border border-white/8 bg-[#10131a] p-4 sm:p-5' in cards

def test_e90_e89_composition_order_survives_polish():
    text=PAGE.read_text(encoding="utf-8")
    markers=[
        "<header",
        'aria-labelledby="research-boundary-title"',
        'aria-labelledby="authority-legend-title"',
        'aria-labelledby="navigable-surfaces-title"',
        'aria-labelledby="gated-capabilities-title"',
        'aria-labelledby="active-evidence-title"',
    ]
    positions=[text.index(marker) for marker in markers]
    assert positions == sorted(positions)

def test_e90_routes_and_accessibility_remain_unchanged():
    text=PAGE.read_text(encoding="utf-8")
    assert 'aria-label="Research navigation"' in text
    assert '<Link href="/research"' in text
    assert '<Link href="/"' in text
    for id_ in ("research-boundary-title","authority-legend-title","navigable-surfaces-title","gated-capabilities-title","active-evidence-title"):
        assert f'aria-labelledby="{id_}"' in text
        assert f'id="{id_}"' in text

def test_e90_gated_card_remains_non_clickable():
    text=CARDS.read_text(encoding="utf-8")
    gated=text.split("export function GatedCapabilityCard",1)[1].split("function Posture",1)[0]
    assert '<SurfaceStatusBadge status="GATED"/>' in gated
    assert "<Link" not in gated
    assert "href=" not in gated
    assert "<button" not in gated

def test_e90_polish_adds_no_runtime_or_authority():
    text=PAGE.read_text(encoding="utf-8")+"\n"+CARDS.read_text(encoding="utf-8")
    for token in ("fetch(", "axios", "useEffect", "useState", 'method:"POST"', 'method:"PUT"',
                  'method:"PATCH"', 'method:"DELETE"', "paperOrder", "brokerOrder",
                  "executeTrade", "repair_action"):
        assert token not in text
