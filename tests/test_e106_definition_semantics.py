from pathlib import Path

COMMAND=Path("frontend/src/app/page.tsx")
CRYPTO=Path("frontend/src/app/components/CryptoQualityDipsStatusPanel.tsx")
EVIDENCE=Path("frontend/src/app/research/page.tsx")
SURFACES=Path("frontend/src/app/research/surfaces/page.tsx")

def test_e106_command_stat_uses_definition_semantics():
    text=COMMAND.read_text(encoding="utf-8")
    assert '<dl className="rounded-2xl border border-white/8 bg-[#10131a] p-4">' in text
    assert '<dt className="text-[11px] uppercase tracking-wider text-zinc-500">{label}</dt>' in text
    assert '<dd className="text-2xl font-semibold text-white mt-1 tabular-nums">{value}</dd>' in text
    assert '{hint && <dd className="text-[11px] text-zinc-600 mt-1">{hint}</dd>}' in text

def test_e106_existing_command_detail_list_remains_native():
    text=COMMAND.read_text(encoding="utf-8")
    assert '<dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">' in text
    assert '<dt className="text-zinc-500">{k}</dt>' in text
    assert '<dd className="text-zinc-200 text-right">{v}</dd>' in text

def test_e106_crypto_metric_and_context_use_definition_semantics():
    text=CRYPTO.read_text(encoding="utf-8")
    assert 'function Metric' in text and 'return <dl className="rounded-xl border border-white/8 bg-black/20 p-3"><dt' in text
    assert '<dd className="mt-1 text-base font-semibold text-zinc-100 tabular-nums">{value}</dd></dl>' in text
    assert 'function Context' in text and 'return <dl className="rounded-lg border border-white/5 px-3 py-2"><dt' in text
    assert '<dd className="inline text-zinc-300">{value}</dd></dl>' in text

def test_e106_forward_evidence_stat_uses_definition_semantics():
    text=EVIDENCE.read_text(encoding="utf-8")
    assert 'function Stat' in text
    assert 'return <dl className="rounded-2xl border border-white/8 bg-[#10131a] p-4"><dt' in text
    assert '<dd className="text-xl font-semibold text-white mt-1">{value}</dd></dl>' in text

def test_e106_definition_semantics_preserve_runtime_and_boundary_contracts():
    command=COMMAND.read_text(encoding="utf-8"); crypto=CRYPTO.read_text(encoding="utf-8"); evidence=EVIDENCE.read_text(encoding="utf-8"); surfaces=SURFACES.read_text(encoding="utf-8")
    assert "/api/live" in command and "}, 8000);" in command
    assert 'REFRESH_MS=15000;' in crypto
    assert "/api/validation/challengers/research-evidence" in evidence and "setInterval(load,15000)" in evidence
    assert "Trading authority stays gated unless a separate validated roadmap execution explicitly unlocks it." in surfaces
