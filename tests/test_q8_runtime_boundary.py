import ast
import copy
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from app.services.paper_epoch_fixture import create_epoch_fixture
from app.services.paper_portfolio_fixture import (
    account_summary_fixture,
    render_portfolio_fixture,
)
from app.services.paper_runtime_boundary import (
    PaperBoundaryRefused,
    PaperReadOnlyPresentation,
    PaperRuntimeBoundary,
)
from app.services.paper_summary_contract import portfolio_payload_fixture
from test_paper_epoch_fixture import STAMP, entry, manifest


def binding(tmp_path):
    store = create_epoch_fixture(tmp_path / "account.sqlite", manifest("q8-account"))
    row = account_summary_fixture(store, now=STAMP, max_age=30)
    payload = portfolio_payload_fixture([row])
    value = [payload]
    adapter = PaperRuntimeBoundary(source=lambda: copy.deepcopy(value[0]),
        expected_accounts=[("HYPERLIQUID_MANUAL", "q8-account")], clock=lambda: STAMP, observation_ttl=30)
    return store, value, adapter


def test_default_inert_and_mutations_never_call_source():
    with pytest.raises(PaperBoundaryRefused, match="UNBOUND"): PaperRuntimeBoundary().snapshot()
    with pytest.raises(PaperBoundaryRefused): PaperReadOnlyPresentation().json()
    def forbidden():
        pytest.fail("Mutation must never invoke a read or write dependency")
    adapter = PaperRuntimeBoundary(source=forbidden)
    for command in (None, {}, {"authorized": True}, {"receipt": "fixture-approved", "action": "EXIT"}):
        with pytest.raises(PaperBoundaryRefused, match="MUTATION_DISABLED"): adapter.submit(command)


def test_injected_disposable_read_presentation_and_immutable_results(tmp_path):
    _, value, adapter = binding(tmp_path)
    result = adapter.snapshot()
    result["accounts"].clear()
    assert len(adapter.snapshot()["accounts"]) == 1
    view = PaperReadOnlyPresentation(adapter)
    assert json.loads(view.json()) == value[0]
    html = view.html()
    for label in ("Gross P&amp;L", "Costs", "Remaining positions", "Source revision", "Financial-event freshness"):
        assert label in html
    assert 'data-paper-presentation-version="2"' in html and "No trading or startup authority" in html


@pytest.mark.parametrize("damage", ["missing", "foreign", "future", "stale", "authority", "extra", "equity", "missing-head"])
def test_incomplete_or_forged_read_evidence_never_publishes(tmp_path, damage):
    _, value, adapter = binding(tmp_path)
    p = value[0]
    if damage == "missing": p["accounts"].clear()
    if damage == "foreign": p["accounts"][0]["epoch"] = "foreign"
    if damage == "future": p["accounts"][0]["observed_at"] += 1
    if damage == "stale":
        row = p["accounts"][0]
        row["observed_at"] -= 31
        row["freshness"]["event_at"] -= 31
    if damage == "authority": p["startup_authorized"] = True
    if damage == "extra": p["write_url"] = "/activate"
    if damage == "equity": p["accounts"][0]["total_equity"] = "1000"
    if damage == "missing-head": p["accounts"][0]["source_head"] = None
    with pytest.raises(PaperBoundaryRefused): adapter.snapshot()


def test_source_failure_has_no_cached_success_or_sensitive_message(tmp_path):
    _, _, adapter = binding(tmp_path)
    adapter.snapshot()
    def broken():
        raise OSError("private source detail fixture")
    adapter.source = broken
    with pytest.raises(PaperBoundaryRefused) as error: adapter.snapshot()
    assert "private source" not in str(error.value) and isinstance(error.value.__cause__, OSError)


def test_unknown_does_not_reset_revision_watermark(tmp_path):
    store, value, adapter = binding(tmp_path)
    initial = copy.deepcopy(value[0])
    adapter.snapshot()
    store.execute(entry(store))
    value[0] = portfolio_payload_fixture([account_summary_fixture(store, now=STAMP, max_age=30)])
    adapter.snapshot()
    with store.connect() as db: db.execute("UPDATE inception SET body='{}'")
    value[0] = portfolio_payload_fixture([account_summary_fixture(store, now=STAMP, max_age=30)])
    assert adapter.snapshot()["accounts"][0]["state"] == "UNKNOWN"
    value[0] = initial
    with pytest.raises(PaperBoundaryRefused): adapter.snapshot()


def test_conflicting_same_revision_refuses(tmp_path):
    _, value, adapter = binding(tmp_path)
    adapter.snapshot()
    value[0]["accounts"][0]["source_head"] = "f" * 64
    with pytest.raises(PaperBoundaryRefused): adapter.snapshot()


def test_concurrent_read_fails_closed_without_reusing_old_success(tmp_path):
    _, value, adapter = binding(tmp_path)
    begun, release = Event(), Event()
    def source():
        begun.set()
        assert release.wait(2)
        return value[0]
    adapter.source = source
    with ThreadPoolExecutor(1) as pool:
        pending = pool.submit(adapter.snapshot)
        assert begun.wait(2)
        with pytest.raises(PaperBoundaryRefused, match="ALREADY_IN_PROGRESS"): adapter.snapshot()
        release.set()
        assert pending.result(timeout=2) == value[0]


def test_q7_v1_html_reconstructs_byte_identically(tmp_path):
    from pathlib import Path

    _, value, _ = binding(tmp_path)
    source = subprocess.check_output(["git", "show", "1d548b3aaa8596a5ba9227675bba3adf4f92576c:backend/app/services/paper_portfolio_fixture.py"]).decode("utf-8")
    tree = ast.parse(source)
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "render_portfolio_fixture")
    neutral = ast.parse((Path(__file__).resolve().parents[1] / "backend/app/services/paper_summary_contract.py").read_text(encoding="utf-8"))
    current = next(n for n in neutral.body if isinstance(n, ast.FunctionDef) and n.name == "render_portfolio_fixture")
    assert ast.dump(function, include_attributes=False) == ast.dump(current, include_attributes=False)
    expected = (b"<table><thead><tr><th>Strategy / epoch</th><th>State</th><th>Reconciled cash</th><th>Realized net</th></tr></thead><tbody>"
                b"<tr><td>HYPERLIQUID_MANUAL / q8-account</td><td>RECONCILED_FIXTURE_ONLY</td><td>1000</td><td>0</td></tr>"
                b"</tbody></table><p>Separate simulated accounts. No combined equity or trading authority.</p>")
    assert render_portfolio_fixture(value[0]).encode() == expected


def test_neutral_boundary_has_no_store_or_operational_imports():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "backend/app"
    for name in ("paper_runtime_boundary.py", "paper_summary_contract.py"):
        text = (root / "services" / name).read_text(encoding="utf-8")
        for forbidden in ("paper_epoch_fixture", "paper_strategy_fixture", "sqlite3", "app.main", "FastAPI", "APIRouter"):
            assert forbidden not in text
    for path in [root / "main.py", *(root / "api").glob("*.py")]:
        assert "paper_runtime_boundary" not in path.read_text(encoding="utf-8-sig")
