"""Two genuine source producers and canonical constructor seams; no runtime."""

import copy
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import digest
from app.services.unified_research_sources import UnifiedResearchSources
from test_hyperliquid_current_producer import fixture as hl_fixture
from test_quality_dips_current_producer import fixture as qd_fixture
from test_quality_dips_current_producer import proof


def pair(monkeypatch):
    import scripts.observation_runtime.personal_coordination_store as native

    q = qd_fixture(monkeypatch)
    h = hl_fixture(monkeypatch, shared_clock=q.s.clock)
    # Dispatch only the two test namespaces in the existing native-memory port.
    roots = {q.s.s.owner.root: q.s.s.files, h.io.owner.root: h.io.files}

    def memory_path(root):
        if root not in roots:
            raise AssertionError("Not a disposable memory namespace")
        return SimpleNamespace(
            iterdir=lambda: [SimpleNamespace(name=n) for n in roots[root]]
        )

    monkeypatch.setattr(native, "Path", memory_path)
    flags = SimpleNamespace(accepted=True, mutate=False)

    def accept(context, *, now):
        if not flags.accepted:
            return False
        assert context["execution_domain"] == "DISPOSABLE"
        assert context["enrollments"] == {"QUALITY_DIPS": q.s.e, "HYPERLIQUID": h.e}
        result = proof(
            "ATLAS_UNIFIED_RESEARCH_VERIFIED_V1", context, execution_domain="DISPOSABLE"
        )
        if flags.mutate:
            context["packets"]["HYPERLIQUID"]["revision"] += 1
        return result

    authority = SimpleNamespace(verify_current=accept)
    joint = UnifiedResearchSources(
        quality_dips=q.owner, hyperliquid=h.owner, authority=authority, clock=q.s.clock
    )
    q.owner.publish_current()
    h.owner.publish_current()
    return SimpleNamespace(**locals())


def test_qd_and_hl_coexist_with_separate_native_protocols_and_no_net_cash(monkeypatch):
    f = pair(monkeypatch)
    before = (copy.deepcopy(f.q.s.s.files), copy.deepcopy(f.h.io.files))
    view = f.joint.read_current()
    assert set(view["lanes"]) == {"QUALITY_DIPS", "HYPERLIQUID"}
    assert view["lanes"]["QUALITY_DIPS"]["currency"] == "USD"
    assert view["lanes"]["HYPERLIQUID"]["currency"] == "USDC"
    assert view["total_cash"] is None and view["total_equity"] is None
    assert view["financial_startup_authorized"] is False
    assert f.joint.read_current() == view
    assert (f.q.s.s.files, f.h.io.files) == before


@pytest.mark.parametrize(
    "damage", ["account", "epoch", "source", "root", "release", "commit"]
)
def test_no_account_source_root_or_release_alias_can_join(monkeypatch, damage):
    f = pair(monkeypatch)
    key = {
        "account": "account_id",
        "epoch": "epoch",
        "source": "source_id",
        "root": "root_id",
        "release": "release_digest",
        "commit": "source_commit",
    }[damage]
    if damage in ("release", "commit"):
        f.h.owner.enrollment[key] = "0" * len(f.h.owner.enrollment[key])
    else:
        f.h.owner.enrollment[key] = copy.deepcopy(f.q.owner.enrollment[key])
    with pytest.raises(ValueError):
        f.joint.read_current()


@pytest.mark.parametrize(
    "damage",
    ["stale-hl", "stale-qd", "authority", "mutation", "missing-lane", "replacement"],
)
def test_unified_reader_refuses_incomplete_or_unaccepted_pair(monkeypatch, damage):
    f = pair(monkeypatch)
    before = (copy.deepcopy(f.q.s.s.files), copy.deepcopy(f.h.io.files))
    if damage == "stale-hl":
        f.q.s.now[0] += 6
    elif damage == "stale-qd":
        f.q.s.now[0] += 31
    elif damage == "authority":
        f.flags.accepted = False
    elif damage == "mutation":
        f.flags.mutate = True
    elif damage == "missing-lane":
        del f.joint.sources["HYPERLIQUID"]
    else:
        f.joint.sources["HYPERLIQUID"] = object()
    with pytest.raises((ValueError, KeyError)):
        f.joint.read_current()
    assert (f.q.s.s.files, f.h.io.files) == before


def canonical_ports(f):
    from app.services.paper_financial_replay import initial_state
    from app.services.paper_market_observers import HyperliquidMarketObserver
    from app.services.perp_resting_writer import RestingPerpWriter
    from app.services.perp_source_planner import PerpSourcePlanner
    from app.services.quality_dips_unified_writer import EnrolledQualityDipsWriter
    from app.services.unified_native_writer import (
        CanonicalWriterLane,
        NativeFinancialWriter,
    )
    from app.services.unified_portfolio_custody import UnifiedPortfolioCustody
    from test_paper_epoch_fixture import manifest as q_manifest

    # The QD writer is an inert contract object: no enrolled financial runtime is
    # constructed or connected. The actual CanonicalWriterLane constructor runs.
    qw = EnrolledQualityDipsWriter.__new__(EnrolledQualityDipsWriter)
    qw.manifest = q_manifest(f.q.s.e["epoch"], "QUALITY_DIPS")
    qw.store = SimpleNamespace(enrollment=f.q.s.e)
    qw.binding = {"SYNTHETIC_QD_READ_ONLY_CONTRACT": True}
    qw.authority = SimpleNamespace(
        verify_lane=lambda binding, parts: (
            binding == qw.binding and parts["writer"] is qw
        )
    )
    qp = SimpleNamespace(reader=SimpleNamespace(source=f.q.owner))
    qlane = CanonicalWriterLane(
        writer=qw,
        observer=object(),
        planner=qp,
        shutdown=object(),
        reports=SimpleNamespace(store=qw.store),
    )

    # Actual NativeFinancialWriter/RestingPerpWriter constructors over an inert
    # verified-cut port. No dispatch, financial publication or account inception.
    state = {
        "pin_schema": "FS2_TEST_PIN_V1",
        "manifest": f.h.parameters,
        "state": initial_state(f.h.parameters),
        "head": "SYNTHETIC-FINANCIAL-HEAD",
        "root": [8, 8, 8],
        "acknowledged_operations": {},
    }
    store = SimpleNamespace(
        verified_cut=lambda: copy.deepcopy(state),
        enrollment=f.h.e,
        remaining_operations=lambda: 128,
    )
    fa = SimpleNamespace()
    fa.verify_components = lambda binding: (
        binding["store"] is store
        and binding["manifest_digest"] == digest(f.h.parameters)
    )
    fa.verify_cut = lambda binding, cut: fa.verify_components(binding) and cut == state
    fw = NativeFinancialWriter(
        store=store,
        authority=fa,
        manifest=f.h.parameters,
        execution_domain="DISPOSABLE_TEST",
    )
    fa.verify_order_components = lambda binding, parts: (
        parts == {"financial": fw, "orders": f.h.orders}
    )
    pw = RestingPerpWriter(financial=fw, orders=f.h.orders)
    fa.verify_planner_components = lambda binding, parts: (
        parts["writer"] is pw and parts["source"] is f.h.owner
    )
    pp = PerpSourcePlanner(
        writer=pw, source=f.h.owner, clock=f.h.clock, session_id="SYNTHETIC-SESSION"
    )
    po = HyperliquidMarketObserver(f.h.adapter, clock=f.h.clock, source=f.h.owner)
    fa.verify_lane = lambda binding, parts: (
        parts["writer"] is pw and parts["observer"] is po and parts["planner"] is pp
    )
    plane = CanonicalWriterLane(
        writer=pw,
        observer=po,
        planner=pp,
        shutdown=object(),
        reports=SimpleNamespace(store=store),
    )
    writers = {"QUALITY_DIPS": qw, "HYPERLIQUID": pw}
    # Explicit non-parity risk port identity; no USD==USDC conversion performed.
    risk = SimpleNamespace(
        source="SYNTHETIC_EXPLICIT_CONVERSION_PORT", declared_usdc_rate="0.97"
    )
    policy = {"policy_id": "SYNTHETIC-NOT-OPERATIONAL"}
    journal = SimpleNamespace(
        manifest={
            "accounts": {k: digest(v.manifest) for k, v in writers.items()},
            "policy_digest": digest(policy),
        }
    )
    ca = SimpleNamespace(
        verify_components=lambda c: (
            c["journal"] is journal and c["risk"] is risk and c["writers"] == writers
        )
    )
    portfolio = UnifiedPortfolioCustody(
        writers=writers,
        journal=journal,
        policy=policy,
        risk=risk,
        ownership=object(),
        authority=ca,
        clock=f.q.s.clock,
    )
    lanes = {"QUALITY_DIPS": qlane, "HYPERLIQUID": plane}

    def accept(context, actual_lanes, actual_portfolio, actual_risk):
        assert (
            actual_lanes == lanes
            and actual_portfolio is portfolio
            and actual_risk is risk
        )
        return proof("ATLAS_UNIFIED_RESEARCH_BINDING_V1", context)

    f.authority.verify_canonical = accept
    return SimpleNamespace(**locals())


def test_actual_canonical_constructor_seams_prepare_without_financial_runtime(
    monkeypatch,
):
    f = pair(monkeypatch)
    c = canonical_ports(f)
    before = (
        copy.deepcopy(f.q.s.s.files),
        copy.deepcopy(f.h.io.files),
        copy.deepcopy(c.state),
    )
    result = f.joint.prepare_canonical_lanes(
        lanes=c.lanes, portfolio=c.portfolio, risk=c.risk
    )
    assert result["verified"] is True
    assert (f.q.s.s.files, f.h.io.files, c.state) == before
    assert c.risk.declared_usdc_rate == "0.97"


@pytest.mark.parametrize(
    "damage",
    ["risk", "currency", "epoch", "writer", "qd-reader", "hl-source", "unknown-lane"],
)
def test_canonical_preparation_cannot_substitute_accounts_sources_or_risk(
    monkeypatch, damage
):
    f = pair(monkeypatch)
    c = canonical_ports(f)
    if damage == "risk":
        c.portfolio.risk = object()
    elif damage == "currency":
        c.pw.manifest["currency"] = "USD"
    elif damage == "epoch":
        c.pw.manifest["epoch"] = "FOREIGN"
    elif damage == "writer":
        c.portfolio.writers["HYPERLIQUID"] = c.qw
    elif damage == "qd-reader":
        c.qp.reader.source = object()
    elif damage == "hl-source":
        c.pp.source = object()
    else:
        c.lanes["OTHER"] = c.plane
    with pytest.raises(ValueError):
        f.joint.prepare_canonical_lanes(
            lanes=c.lanes, portfolio=c.portfolio, risk=c.risk
        )


@pytest.mark.parametrize("damage", ["planner", "writer", "risk", "policy", "clock"])
def test_canonical_callback_cannot_change_prepared_components(monkeypatch, damage):
    f = pair(monkeypatch)
    c = canonical_ports(f)
    original = f.authority.verify_canonical

    def changing(*args):
        receipt = original(*args)
        if damage == "planner":
            c.pp.source = object()
        elif damage == "writer":
            c.plane.writer = c.qw
        elif damage == "risk":
            c.portfolio.risk = object()
        elif damage == "policy":
            c.portfolio.policy["policy_id"] = "OTHER"
        else:
            c.portfolio.clock = lambda: 0
        return receipt

    f.authority.verify_canonical = changing
    with pytest.raises(ValueError):
        f.joint.prepare_canonical_lanes(
            lanes=c.lanes, portfolio=c.portfolio, risk=c.risk
        )


def test_unified_authority_cannot_authenticate_with_plain_true(monkeypatch):
    f = pair(monkeypatch)
    f.authority.verify_current = lambda *a, **k: True
    with pytest.raises(ValueError, match="AUTHORITY_UNVERIFIED"):
        f.joint.read_current()
