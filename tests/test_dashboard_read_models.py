"""In-memory producers/accounts and ASGI only. No native or installed host."""

import copy
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.services.dashboard_read_models import DashboardAccountRead, DashboardReadModels
from app.services.paper_financial_replay import body, digest
from fastapi.testclient import TestClient
from test_quality_dips_current_producer import proof
from test_unified_research_sources import pair

from scripts.observation_runtime.dashboard_read_contracts import (
    MODEL,
    PANES,
    SELECTED,
    build_app,
)

ROOT = Path(__file__).resolve().parents[1]


def system(monkeypatch, *, financial=False):
    f = pair(monkeypatch)
    scope = {
        k: {n: s.enrollment[n] for n in ("account_id", "epoch")}
        for k, s in f.joint.sources.items()
    }
    cuts = {
        "schema": "ATLAS_UNIFIED_ACCOUNT_CUTS_V1",
        "state": "ACKNOWLEDGED",
        "accounts": {},
        "startup_authorized": False,
        "total_cash": None,
        "total_equity": None,
    }
    for lane, currency in (("QUALITY_DIPS", "USD"), ("HYPERLIQUID", "USDC")):
        cuts["accounts"][lane] = {
            "epoch": scope[lane]["epoch"],
            "strategy": lane,
            "currency": currency,
            "source_revision": 2,
            "source_head": digest([lane, "synthetic-head"]),
            "observed_at": f.q.s.now[0],
            "opening_cash": "1000",
            "cash": "999.125",
            "available_cash": "950",
            "gross": "0.5",
            "realized_costs": "0.2",
            "net": "0.3",
            "fees": None,
            "slippage": None,
            "funding": None,
            "positions": {},
            "resting_orders": {},
            "valuation": None,
            "valuation_status": "UNAVAILABLE",
        }
    flags = SimpleNamespace(valid=True, mutate=False, domain="DISPOSABLE")
    reader = SimpleNamespace(read=lambda: copy.deepcopy(cuts))

    def verify(context, *, now):
        if not flags.valid:
            return False
        assert context == {
            "scope": scope,
            "execution_domain": "DISPOSABLE",
            "accounts": cuts,
        }
        receipt = proof(
            "ATLAS_DASHBOARD_ACCOUNTS_VERIFIED_V1",
            context,
            execution_domain=flags.domain,
        )
        if flags.mutate:
            context["accounts"]["accounts"]["QUALITY_DIPS"]["cash"] = "999999"
        return receipt

    authority = SimpleNamespace(verify_read=verify)
    accounts = DashboardAccountRead(
        reader=reader,
        authority=authority,
        scope=scope,
        clock=f.q.s.clock,
        execution_domain="DISPOSABLE",
    )
    models = DashboardReadModels(
        research=f.joint, clock=f.q.s.clock, accounts=accounts if financial else None
    )
    return SimpleNamespace(**locals())


def test_current_two_source_contract_does_not_invent_financial_or_connection_state(
    monkeypatch,
):
    s = system(monkeypatch)
    files = copy.deepcopy((s.f.q.s.s.files, s.f.h.io.files))
    view = s.models.snapshot()
    assert (
        view["schema"] == "ATLAS_DASHBOARD_READ_MODEL_V1"
        and view["execution_domain"] == "DISPOSABLE"
    )
    assert (
        view["accounts"]["state"] == "UNAVAILABLE"
        and view["accounts"]["accounts"] is None
    )
    assert view["total_cash"] is view["total_equity"] is None
    for lane in view["lanes"].values():
        assert (
            lane["research"]["status"] == "FRESH"
            and lane["connection"] == "UNAVAILABLE"
        )
        assert lane["research"]["source"]["digest"]
        assert (
            lane["research"]["completeness"]
            == "ACCEPTED_SOURCE_CUT_NOT_FULL_MARKET_COVERAGE"
        )
    assert all(
        view[k]["status"] == "UNAVAILABLE" for k in ("runtime", "stop", "continuation")
    )
    assert not view["startup_authorized"]
    assert body(view) == body(s.models.snapshot())
    assert view["snapshot_id"] == digest(
        {k: v for k, v in view.items() if k != "snapshot_id"}
    )
    assert (s.f.q.s.s.files, s.f.h.io.files) == files


def test_separate_account_wire_contract_retains_exact_decimals_and_identity(
    monkeypatch,
):
    s = system(monkeypatch, financial=True)
    before = copy.deepcopy(s.cuts)
    view = s.models.snapshot()
    assert view["accounts"] == before
    assert view["account_scope"] == s.scope
    assert view["accounts"]["accounts"]["QUALITY_DIPS"]["currency"] == "USD"
    assert view["accounts"]["accounts"]["HYPERLIQUID"]["currency"] == "USDC"
    assert view["accounts"]["accounts"]["QUALITY_DIPS"]["cash"] == "999.125"
    assert s.cuts == before and not view["startup_authorized"]


def test_missing_sources_are_explicitly_unavailable():
    m = DashboardReadModels(research=None, clock=lambda: 100)
    view = m.snapshot()
    assert view["execution_domain"] == "UNAVAILABLE" and view["account_scope"] is None
    assert all(r["research"]["status"] == "UNAVAILABLE" for r in view["lanes"].values())


@pytest.mark.parametrize("net", ["0.33333333", "0.33"])
def test_financial_read_arithmetic_does_not_depend_on_ambient_precision(
    monkeypatch, net
):
    from decimal import localcontext

    s = system(monkeypatch, financial=True)
    a = s.cuts["accounts"]["QUALITY_DIPS"]
    a.update(gross="0.55555555", realized_costs="0.22222222", net=net)
    with localcontext() as ambient:
        ambient.prec = 2
        view = s.models.snapshot()
    assert view["accounts"]["state"] == (
        "ACKNOWLEDGED" if net == "0.33333333" else "UNKNOWN"
    )


def test_read_model_route_discards_final_cut_failure(monkeypatch):
    s = system(monkeypatch)
    s.models.research = object()
    with TestClient(
        build_app(models=s.models, port=8765), base_url="http://127.0.0.1:8765"
    ) as client:
        response = client.get(MODEL)
    assert response.status_code == 503 and response.json()["status"] == "UNKNOWN"


@pytest.mark.parametrize(
    "damage",
    [
        "stale",
        "future",
        "currency",
        "epoch",
        "missing-lane",
        "missing-cash",
        "net",
        "negative-cash",
        "number-cash",
        "revision-bool",
        "negative-revision",
        "positions",
        "reserved-cash",
        "total",
        "schema",
        "unknown",
        "authority",
        "plain-true",
        "receipt-domain",
        "mutation",
        "changed-during-read",
    ],
)
def test_invalid_financial_evidence_clears_both_accounts(monkeypatch, damage):
    s = system(monkeypatch, financial=True)
    a = s.cuts["accounts"]["HYPERLIQUID"]
    if damage == "stale":
        a["observed_at"] -= 6
    elif damage == "future":
        a["observed_at"] += 1
    elif damage == "currency":
        a["currency"] = "USD"
    elif damage == "epoch":
        a["epoch"] = "OTHER"
    elif damage == "missing-lane":
        del s.cuts["accounts"]["QUALITY_DIPS"]
    elif damage == "missing-cash":
        del a["cash"]
    elif damage == "net":
        a["net"] = "0.4"
    elif damage == "negative-cash":
        a["cash"] = "-1"
    elif damage == "number-cash":
        a["cash"] = 1000
    elif damage == "revision-bool":
        a["source_revision"] = True
    elif damage == "negative-revision":
        a["source_revision"] = -1
    elif damage == "positions":
        a["positions"] = {
            "p": {"symbol": "BTC", "side": "LONG", "quantity": "1", "remaining": "2"}
        }
    elif damage == "reserved-cash":
        a["resting_orders"] = {"o": {"state": "RESERVED"}}
    elif damage == "total":
        s.cuts["total_cash"] = "1999"
    elif damage == "schema":
        s.cuts["schema"] = "OTHER"
    elif damage == "unknown":
        s.cuts["state"] = "UNKNOWN"
    elif damage == "authority":
        s.flags.valid = False
    elif damage == "plain-true":
        s.authority.verify_read = lambda *a, **k: True
    elif damage == "receipt-domain":
        s.flags.domain = "OPERATIONAL"
    elif damage == "mutation":
        s.flags.mutate = True
    else:
        calls = [0]

        def read():
            calls[0] += 1
            if calls[0] > 1:
                s.cuts["accounts"]["HYPERLIQUID"]["source_revision"] += 1
            return copy.deepcopy(s.cuts)

        s.reader.read = read
    view = s.models.snapshot()
    assert (
        view["accounts"]["state"] == "UNKNOWN" and view["accounts"]["accounts"] is None
    )


@pytest.mark.parametrize(
    "damage", ["rollback", "same-revision-conflict", "domain", "source-account"]
)
def test_scope_and_revision_continuity_cannot_be_rebound(monkeypatch, damage):
    s = system(monkeypatch, financial=True)
    assert s.models.snapshot()["accounts"]["state"] == "ACKNOWLEDGED"
    if damage == "rollback":
        s.cuts["accounts"]["QUALITY_DIPS"]["source_revision"] -= 1
    elif damage == "same-revision-conflict":
        s.cuts["accounts"]["QUALITY_DIPS"]["cash"] = "999.0"
    elif damage == "domain":
        s.accounts.execution_domain = "OPERATIONAL"
    else:
        s.accounts.scope["QUALITY_DIPS"]["account_id"] = "FOREIGN"
    view = s.models.snapshot()
    assert (
        view["accounts"]["state"] == "UNKNOWN" and view["accounts"]["accounts"] is None
    )


def test_expired_research_never_reappears_as_current_data(monkeypatch):
    s = system(monkeypatch)
    assert s.models.snapshot()["lanes"]["HYPERLIQUID"]["research"]["status"] == "FRESH"
    s.f.q.s.now[0] += 6
    view = s.models.snapshot()
    assert view["lanes"]["HYPERLIQUID"]["research"]["status"] == "STALE"
    assert all(x["research"]["data"] is None for x in view["lanes"].values())
    assert view["accounts"]["accounts"] is None


def test_lost_source_authority_is_unknown_even_before_age_limit(monkeypatch):
    s = system(monkeypatch)
    s.models.snapshot()
    s.f.flags.accepted = False
    view = s.models.snapshot()
    assert all(x["research"]["status"] == "UNKNOWN" for x in view["lanes"].values())


@pytest.mark.parametrize("route", list(PANES))
def test_original_six_pane_urls_are_safe_readonly_contract_surfaces(monkeypatch, route):
    s = system(monkeypatch)
    app = build_app(models=s.models, port=8765)
    with TestClient(app, base_url="http://127.0.0.1:8765") as c:
        r = c.get(route)
        assert r.status_code == 200 and PANES[route][1] in r.text
        assert (
            "dashboard_read_contract.js" in r.text and "PAPER startup blocked" in r.text
        )
        assert "no-store" in r.headers["cache-control"]


def test_original_shell_assets_and_unknown_selected_state_are_compatible(monkeypatch):
    s = system(monkeypatch)
    app = build_app(models=s.models, port=8765)
    with TestClient(app, base_url="http://127.0.0.1:8765") as c:
        assert (
            c.get("/dashboard").content
            == (ROOT / "backend/app/static/dashboard_hub.html").read_bytes()
        )
        for route in PANES:
            assert route in c.get("/dashboard").text
        for leaf in ("runtime_poll.js", "dashboard_read_contract.js", "atlas_ui.css"):
            assert c.get("/static/" + leaf).status_code == 200
        assert c.get("/dashboard/perps?embed=1").status_code == 200
        selected = c.get(SELECTED).json()
        assert (
            selected["status"] == "UNAVAILABLE"
            and selected["cash"] is selected["positions"] is None
        )
        assert c.get("/health").json()["financial_writers"] is False
        assert c.get("/api/perps/manual/positions").status_code == 503
        assert "COMING SOON" in c.get("/dashboard").text


@pytest.mark.parametrize(
    "method,path,headers",
    [
        ("POST", "/_atlas/control/stop", {}),
        ("POST", SELECTED + "/commands", {}),
        ("DELETE", MODEL, {}),
        ("GET", MODEL, {"Host": "foreign"}),
        ("GET", MODEL, {"Origin": "http://foreign"}),
        ("GET", MODEL, {"Sec-Fetch-Site": "cross-site"}),
        ("GET", MODEL + "?scope=OTHER", {}),
        ("GET", "/config/alpaca.env", {}),
    ],
)
def test_http_boundary_never_dispatches_writes_or_legacy_gets(
    monkeypatch, method, path, headers
):
    s = system(monkeypatch, financial=True)
    before = copy.deepcopy((s.cuts, s.f.q.s.s.files, s.f.h.io.files))
    app = build_app(models=s.models, port=8765)
    with TestClient(app, base_url="http://127.0.0.1:8765") as c:
        assert c.request(method, path, headers=headers).status_code in (403, 404)
    assert (s.cuts, s.f.q.s.s.files, s.f.h.io.files) == before


def test_repeated_asgi_gets_have_no_financial_or_source_publication_effect(monkeypatch):
    s = system(monkeypatch, financial=True)
    before = copy.deepcopy((s.cuts, s.f.q.s.s.files, s.f.h.io.files))
    app = build_app(models=s.models, port=8765)
    with TestClient(app, base_url="http://127.0.0.1:8765") as c:
        first = c.get(MODEL).json()
        for _ in range(3):
            assert c.get(MODEL).json() == first
    assert (s.cuts, s.f.q.s.s.files, s.f.h.io.files) == before


def test_frontend_consumers_reject_stale_and_unsupported_financial_views(
    monkeypatch, tmp_path
):
    s = system(monkeypatch, financial=True)
    view = s.models.snapshot()
    data = tmp_path / "read-model.json"
    data.write_text(json.dumps(view), encoding="utf-8")
    code = r"""
const assert=require('node:assert/strict');const fs=require('fs');
const model=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));
const ui=require('./backend/app/static/dashboard_read_contract.js');
const old=require('./backend/app/static/quality_dips_selected_paper.js');
const now=model.observed_at*1000;
assert.match(ui.render(model,now,'quality'),/999\.125 USD/);
assert.match(ui.render(model,now,'perps'),/999\.125 USDC/);
assert.doesNotMatch(ui.render(model,now+6000,'quality'),/999\.125/);
assert.match(ui.render(model,now+6000,'perps'),/STALE/);
assert.match(ui.render(model,now,'prediction'),/UNAVAILABLE/);
assert.match(ui.render(model,now,'command'),/Stop UNAVAILABLE/);
const compatibility={schema:'ATLAS_UNIFIED_PAPER_VIEW_V1',state:'STOPPED',financial_state:'READ_SEPARATE_ACCOUNTS',startup_authorized:false,total_cash:null,total_equity:null,lanes:{QUALITY_DIPS:null,HYPERLIQUID:null},accounts:model.accounts};
assert.match(old.renderUnified(compatibility,now),/999\.125 USD/);
assert.match(old.renderUnified(compatibility,now),/999\.125 USDC/);
const bad=structuredClone(model);bad.total_cash='1999';assert.match(ui.render(bad,now,'quality'),/UNKNOWN/);
const attack=structuredClone(model);attack.lanes.QUALITY_DIPS.research.source.source_id='<script>bad</script>';
assert.doesNotMatch(ui.render(attack,now,'quality'),/<script>bad/);
assert.match(ui.render(attack,now,'quality'),/&lt;script&gt;/);
    console.log('Renderer/compatibility assertions passed; no browser acknowledgement');
"""
    result = subprocess.run(
        ["node", "-e", code, str(data)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_contract_panes_use_shared_hidden_frame_polling_and_clear_transport_failures(
    monkeypatch, tmp_path
):
    s = system(monkeypatch, financial=True)
    data = tmp_path / "model.json"
    data.write_text(json.dumps(s.models.snapshot()), encoding="utf-8")
    code = r"""
const assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
const model=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));
let visible=false,calls=0,offline=false,now=model.observed_at*1000,html='',text='';
const target={get innerHTML(){return html},set innerHTML(v){html=v;text=''},get textContent(){return text},set textContent(v){text=v;html=''}};
const ticks=[],document={hidden:true,body:{dataset:{atlasPane:'quality'}},getElementById:id=>id==='atlas-read-model'?target:null};
const ctx=vm.createContext({document,window:{frameElement:{closest:()=>({classList:{contains:()=>visible}})}},Date:class extends Date {static now(){return now}},AbortController,setTimeout:()=>0,clearTimeout:()=>{},setInterval:fn=>ticks.push(fn),fetch:async()=>{calls++;if(offline)throw Error('offline');return {ok:true,json:async()=>model}}});
vm.runInContext(fs.readFileSync('backend/app/static/runtime_poll.js','utf8'),ctx);
vm.runInContext(fs.readFileSync('backend/app/static/dashboard_read_contract.js','utf8'),ctx);
(async()=>{
assert.equal(calls,0);document.hidden=false;await ticks[0]();assert.equal(calls,0);
visible=true;await ticks[0]();assert.equal(calls,1);assert.match(html,/999\.125 USD/);
visible=false;await ticks[0]();assert.equal(calls,1);
visible=true;now+=6000;ticks[1]();assert.doesNotMatch(html,/999\.125/);assert.match(html,/STALE/);assert.equal(calls,1);
offline=true;await ticks[0]();assert.equal(calls,2);assert.equal(html,'');assert.match(text,/UNAVAILABLE/);
console.log('Hidden-frame, expiry and transport-failure contracts passed; no real browser');
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    result = subprocess.run(
        ["node", "-e", code, str(data)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
