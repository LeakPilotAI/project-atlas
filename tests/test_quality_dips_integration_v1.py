"""Real FS2/FS3 protocol logic with injected ordinary-file primitives, not native acceptance."""
import copy
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from app.api.quality_dips_selected_paper import create_router, financial_view
from app.investment.quality_dips_candidate_evidence import CandidateEvidenceAdapter
from app.investment.quality_dips_selected_account import (
    FinancialStorePublisher,
    SelectedAccountDispatcher,
)
from app.services.paper_financial_replay import body, digest, strict
from qd_integration_harness import (
    Admission,
    ExecutionAuthority,
    Manual,
    RankingAuthority,
    fs_bundle,
)
from test_quality_dips_selected_policy import setup_case


def bundle_for(symbol="MSFT", asset="STOCK"):
    manifest, original = setup_case(symbol, asset)
    now = original["timestamp"]
    ladder = {"ready": True, "levels": [{"level": "L1", "reached": True, "limit_price": 40.0}]}
    prediction = {"patient_state": "ACCUMULATION", "entry_ladder": ladder, "blockers": []}
    observation = {"observation_id": "synthetic-observation-" + symbol, "symbol": symbol,
                   "strategy_version": "QUALITY_DIPS_V3", "policy_version": "quality-dips-v3-mos-15-20-25-30-v1",
                   "evidence_class": "FORWARD_COLLECTION", "classification": "ACCUMULATION", "missing_data": [],
                   "execution": "MANUAL_ONLY", "source_timestamp": datetime.fromtimestamp(now, UTC).isoformat(),
                   "timestamp": datetime.fromtimestamp(now, UTC).isoformat(),
                   "prediction": prediction}
    row = {"symbol": symbol, "asset_type": asset, "opportunity_score": 87.5,
           "reasons": ["SYNTHETIC reached ladder and quality evidence"], "blockers": [], "missing_critical": [],
           "quality_dips_v2": {"quality_dips_v3": prediction}}
    instrument = {"symbol": symbol, "instrument_id": "synthetic:" + symbol, "asset_class": asset,
                  "currency": "USD", "units": "SHARES", "long_supported": True, "fractional": True, "rules_revision": "fixture-r1"}
    quote = {"symbol": symbol, "instrument_id": instrument["instrument_id"], "source": "synthetic-price",
             "effective_timestamp": datetime.fromtimestamp(now, UTC).isoformat(), "execution_price": "40"}
    bundle = {"board": [row], "observation": observation, "instrument": instrument, "quote": quote,
              "publication": {"schema": "QD_RANKING_REVISION_V1", "generation": 1, "source_revision": 1,
                              "issuer": "synthetic-ranking", "cohort_id": "synthetic-board-50", "issued_at": now,
                              "expires_at": now + 300, "state": "ACTIVE"}}
    manifest["schema"] = "PAPER_EPOCH_SELECTED_QD_V3"
    policy = manifest["account_policy"]
    policy.pop("ranking_receipts")
    policy.update(schema="QD_SELECTED_ACCOUNT_POLICY_V2", account_id="synthetic-selected", ranking_authority="synthetic-ranking")
    return manifest, bundle, now


def system(tmp_path, symbol="MSFT", asset="STOCK", *, fractional=True):
    manifest, bundle, stamp = bundle_for(symbol, asset)
    manifest["account_policy"]["instruments"][symbol]["fractional"] = fractional
    bundle["instrument"]["fractional"] = fractional
    now = [stamp]
    admission = Admission(tmp_path / "admission.json")
    ranking, execution, manual = RankingAuthority(admission, bundle), ExecutionAuthority(bundle["instrument"], bundle["quote"]), Manual()
    evidence = CandidateEvidenceAdapter(ranking_authority=ranking, execution_authority=execution)
    store, target, reopen = fs_bundle(tmp_path, manifest, lambda: now[0])
    current = {}

    class Projection:
        def verify(self, receipt):
            with store.guard():
                pin, _, _, _, _, operations, _ = store._load()
                found = operations.get(receipt["operation_id"])
                if not found or body(found[1]) != body(receipt):
                    return False
                proof = store._read(f"{receipt['source_revision']:04d}-ack.json", pin["entries"][receipt["source_revision"] - 1]["ack"])["projection"]
                context = target._read(proof["prefix"] + "-intent.json", proof["intent"])["context"]
                target.verify(context, proof)
                current.update(context=context, proof=proof, receipt=receipt, observed_at=now[0])
                return True

    publisher = FinancialStorePublisher(store=store, manifest=manifest,
        scope_verifier=lambda actual, expected: digest(actual._load()[1]) == expected)
    projection = Projection()

    def dispatcher():
        return SelectedAccountDispatcher(manifest=manifest, owner={"run_id": "fixture-run", "process_identity": "fixture-child", "resource_id": "fixture-store"},
            evidence=evidence, admission=admission, manual=manual, publisher=publisher, projection=projection, clock=lambda: now[0])

    service = dispatcher()

    class Reader:
        def read_committed(self, account, epoch):
            if not current or any(row["status"] != "ACKNOWLEDGED" for row in admission.load()["operations"].values()):
                return {"status": "UNKNOWN"}
            proof = current["proof"]
            target.verify(current["context"], proof)
            state = target._read(proof["prefix"] + "-view.json", proof["view"])
            return {"schema": "QD_COMMITTED_PROJECTION_V1", "account_id": account, "epoch": epoch,
                    "status": "ACKNOWLEDGED", "state": state, "observed_at": current["observed_at"],
                    "source_revision": current["receipt"]["source_revision"], "source_identity": proof,
                    "policy_digest": digest(manifest["account_policy"]), "report_status": "UNAVAILABLE"}

    reader = Reader()

    class ReadVerifier:
        def verify(self, payload, *, account_id, epoch, now):
            expected = reader.read_committed(account_id, epoch)
            return {"verified": body(expected) == body(payload), "binding": digest(expected)}

    def read():
        return financial_view(reader=reader, verifier=ReadVerifier(), clock=lambda: now[0], account_id=service.account, epoch=service.epoch)

    def entry(operation="entry", quantity="2.5"):
        return {"kind": "ENTRY", "operation_id": operation, "quantity": quantity, "expected_source_revision": 0,
                "timestamp": now[0], "approval": None, "candidate": evidence.candidate(bundle, level="L1", now=now[0])}

    def approve(request):
        request["approval"] = manual.grant(strict(service.approval_context(request)))
        return request

    def exit_request(quantity, operation="exit"):
        state = publisher.snapshot()
        ident, position = next(iter(state["positions"].items()))
        quote = {**bundle["quote"], "execution_price": "44", "effective_timestamp": datetime.fromtimestamp(now[0], UTC).isoformat()}
        execution.allowed.add(digest({"instrument": bundle["instrument"], "quote": quote}))
        return {"kind": "EXIT", "operation_id": operation, "quantity": quantity, "expected_source_revision": state["revision"],
                "timestamp": now[0], "approval": None, "position_id": ident, "expected_position_revision": position["revision"],
                "instrument": bundle["instrument"], "quote": quote}

    return SimpleNamespace(**locals())


@pytest.mark.parametrize("symbol,asset", [("MSFT", "STOCK"), ("AAPL", "STOCK"), ("SPY", "ETF"), ("QQQ", "ETF")])
def test_research_to_fs2_fs3_and_read_only_view(tmp_path, symbol, asset):
    s = system(tmp_path, symbol, asset)
    request = s.approve(s.entry())
    result = s.service.execute(request)
    assert result["status"] == "ACKNOWLEDGED"
    assert s.service.execute(request) == result
    view = s.read()
    assert view["cash"] == "900.0" and view["source_revision"] == 1
    assert view["valuation"] is None and len(view["positions"]) == 1
    s.now[0] += 86400
    partial = s.approve(s.exit_request("1"))
    assert s.service.execute(partial)["status"] == "ACKNOWLEDGED"
    assert next(iter(s.read()["positions"].values()))["remaining"] == "1.5"
    final = s.approve(s.exit_request("1.5", "final"))
    assert s.service.execute(final)["status"] == "ACKNOWLEDGED"
    assert not s.read()["positions"] and s.read()["realized"]["net"] == "9.920"
    assert s.reopen().snapshot()["state"]["revision"] == 3


@pytest.mark.parametrize("damage", ["expired", "future", "tombstone", "replaced", "unsupported", "fractional", "quote", "stale-price", "missing-reasons"])
def test_candidate_failures_are_refusals(tmp_path, damage):
    s = system(tmp_path)
    bundle = copy.deepcopy(s.bundle)
    if damage == "expired": bundle["publication"]["expires_at"] = s.now[0]
    if damage == "future": bundle["publication"]["issued_at"] += 1
    if damage == "tombstone": bundle["publication"]["state"] = "REVOKED"
    if damage == "replaced": s.ranking.current = "different"
    if damage == "unsupported": bundle["instrument"]["asset_class"] = "CRYPTO"
    if damage == "fractional": bundle["instrument"]["fractional"] = "yes"
    if damage == "quote": bundle["quote"]["execution_price"] = "41"
    if damage == "stale-price": bundle["quote"]["effective_timestamp"] = s.now[0] - 31
    if damage == "missing-reasons": bundle["board"][0]["reasons"] = []
    if damage != "replaced": s.ranking.current = digest(bundle)
    with pytest.raises(ValueError): s.evidence.candidate(bundle, level="L1", now=s.now[0])
    assert not s.store.trust.current()["entries"]


@pytest.mark.parametrize("damage", ["cancel", "substitute", "limit", "precision", "stale-revision", "ownership"])
def test_dispatcher_refuses_before_intent(tmp_path, damage):
    s = system(tmp_path)
    request = s.approve(s.entry())
    if damage == "cancel": s.manual.approvals.clear()
    if damage == "substitute": request["quantity"] = "1"
    if damage in ("limit", "precision", "stale-revision"):
        request = s.entry(quantity="2.51" if damage == "limit" else "2.50000000000000000000000000001" if damage == "precision" else "2")
        if damage == "stale-revision": request["expected_source_revision"] = 1
        s.approve(request)
    if damage == "ownership": s.admission.verify_owner = lambda *args: {"verified": False}
    with pytest.raises(ValueError): s.service.execute(request)
    assert not s.store.trust.current()["entries"]
    assert {p.name for p in s.store.output.root.iterdir()} == {"inception.json"}


def test_current_generation_replaces_without_rewriting_inception(tmp_path):
    s = system(tmp_path)
    before = (s.store.output.root / "inception.json").read_bytes()
    s.bundle["publication"].update(generation=2, source_revision=2)
    s.ranking.replace(s.bundle)
    request = s.approve(s.entry())
    assert s.service.execute(request)["status"] == "ACKNOWLEDGED"
    assert strict(request["candidate"])["generation"] == 2
    assert (s.store.output.root / "inception.json").read_bytes() == before


def test_invalidation_after_approval_prevents_publication(tmp_path):
    s = system(tmp_path)
    request = s.approve(s.entry())
    replacement = copy.deepcopy(s.bundle)
    replacement["publication"].update(generation=2, state="REVOKED")
    s.ranking.replace(replacement)
    with pytest.raises(ValueError): s.service.execute(request)
    assert not s.store.trust.current()["entries"]


@pytest.mark.parametrize("failure", ["projection", "after-commit", "admission-finish"])
def test_unknown_never_replays_financial_effect(tmp_path, failure):
    s = system(tmp_path)
    request = s.approve(s.entry())
    if failure == "projection": s.store.projection = None
    if failure == "after-commit":
        original = s.publisher.execute
        def lose_ack(*args, **kwargs):
            original(*args, **kwargs)
            raise OSError("fixture crash after commit")
        s.publisher.execute = lose_ack
    if failure == "admission-finish":
        original_finish = s.admission.finish
        def fail_finish(operation, result):
            if result["status"] == "ACKNOWLEDGED": raise OSError("fixture report/ack failure")
            original_finish(operation, result)
        s.admission.finish = fail_finish
    assert s.service.execute(request)["status"] == "UNKNOWN"
    assert s.service.execute(request)["status"] == "UNKNOWN"
    assert s.dispatcher().execute(request)["status"] == "UNKNOWN"
    assert s.read()["status"] != "ACKNOWLEDGED"


def test_get_and_unregistered_router_have_no_write_capabilities(tmp_path):
    s = system(tmp_path)
    s.service.execute(s.approve(s.entry()))
    before = {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    router = create_router(reader=s.reader, verifier=s.ReadVerifier(), clock=lambda: s.now[0], account_id=s.service.account, epoch=s.service.epoch)
    assert router.routes[0].endpoint()["status"] == "ACKNOWLEDGED"
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error: router.routes[1].endpoint({})
    assert error.value.status_code == 403
    assert before == {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


@pytest.mark.parametrize("damage", ["foreign", "stale", "forged", "exception"])
def test_untrusted_read_results_never_fall_back_to_legacy_cash(tmp_path, damage):
    s = system(tmp_path)
    s.service.execute(s.approve(s.entry()))
    payload = s.reader.read_committed(s.service.account, s.service.epoch)
    if damage == "foreign": payload["epoch"] = "legacy"
    if damage == "stale": payload["observed_at"] -= 31
    if damage == "forged": payload["state"]["cash"] = "999999"
    def read(*args):
        if damage == "exception": raise OSError("fixture unavailable")
        return payload
    reader = SimpleNamespace(read_committed=read)
    view = financial_view(reader=reader, verifier=s.ReadVerifier(), clock=lambda: s.now[0], account_id=s.service.account, epoch=s.service.epoch)
    assert view["status"] != "ACKNOWLEDGED" and view["cash"] is None


def test_concurrent_duplicate_dispatchers_publish_once(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    s = system(tmp_path)
    request = s.approve(s.entry())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda service: service.execute(request), [s.service, s.dispatcher()]))
    assert results[0] == results[1] and results[0]["status"] == "ACKNOWLEDGED"
    assert len(s.store.trust.current()["entries"]) == 1
    assert len(s.manual.used) == 1


def test_invalidation_excluded_until_financial_acknowledgement(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    s = system(tmp_path)
    request = s.approve(s.entry())
    publishing, attempted, invalidated = Event(), Event(), Event()
    original = s.publisher.execute

    def publish(*args, **kwargs):
        publishing.set()
        assert attempted.wait(2)
        assert not invalidated.wait(0.05)
        return original(*args, **kwargs)

    def invalidate():
        assert publishing.wait(2)
        attempted.set()
        bundle = copy.deepcopy(s.bundle)
        bundle["publication"]["state"] = "REVOKED"
        s.ranking.replace(bundle)
        invalidated.set()

    s.publisher.execute = publish
    with ThreadPoolExecutor(max_workers=2) as pool:
        write = pool.submit(s.service.execute, request)
        change = pool.submit(invalidate)
        assert write.result(timeout=5)["status"] == "ACKNOWLEDGED"
        change.result(timeout=5)
    assert invalidated.is_set() and len(s.store.trust.current()["entries"]) == 1


def test_manual_replay_and_one_position_refuse_without_more_effects(tmp_path):
    s = system(tmp_path)
    first = s.approve(s.entry())
    s.service.execute(first)
    second = s.entry("second")
    second["expected_source_revision"] = 1
    second["approval"] = first["approval"]
    with pytest.raises(ValueError): s.service.execute(second)
    s.approve(second)
    with pytest.raises(ValueError, match="ONE_POSITION"): s.service.execute(second)
    assert len(s.store.trust.current()["entries"]) == 1


def test_unknown_blocks_new_operation_after_restart(tmp_path):
    s = system(tmp_path)
    request = s.approve(s.entry())
    s.store.projection = None
    assert s.service.execute(request)["status"] == "UNKNOWN"
    new = s.entry("different")
    assert s.dispatcher().execute(new)["status"] == "UNKNOWN"


@pytest.mark.parametrize("damage", ["inaccessible", "future-fraction", "bool-generation", "duplicate-symbol", "prediction-conflict", "missing-observation"])
def test_adversarial_source_shapes_refuse(tmp_path, damage):
    s = system(tmp_path)
    b = copy.deepcopy(s.bundle)
    if damage == "inaccessible": s.evidence.ranking_authority = None
    if damage == "future-fraction": b["quote"]["effective_timestamp"] = datetime.fromtimestamp(s.now[0], UTC).isoformat().replace("+00:00", ".500000+00:00")
    if damage == "bool-generation": b["publication"]["generation"] = True
    if damage == "duplicate-symbol": b["board"].append(copy.deepcopy(b["board"][0]))
    if damage == "prediction-conflict": b["observation"]["classification"] = "GENERATIONAL"
    if damage == "missing-observation": b["observation"].pop("observation_id")
    s.ranking.current = digest(b)
    with pytest.raises((ValueError, KeyError, AttributeError)):
        s.evidence.candidate(b, level="L1", now=s.now[0])
    assert not s.store.trust.current()["entries"]


def test_get_never_calls_extraneous_writer_provider_capabilities(tmp_path):
    s = system(tmp_path)
    s.service.execute(s.approve(s.entry()))
    forbidden = []
    def unexpected(*args, **kwargs):
        forbidden.append(True)
        raise AssertionError("FORBIDDEN")
    reader = SimpleNamespace(read_committed=s.reader.read_committed, refresh=unexpected, publish=unexpected,
                             close_positions=unexpected, clear_unknown=unexpected, start=unexpected)
    assert financial_view(reader=reader, verifier=s.ReadVerifier(), clock=lambda: s.now[0],
                          account_id=s.service.account, epoch=s.service.epoch)["status"] == "ACKNOWLEDGED"
    assert not forbidden


def test_router_remains_unregistered_and_modules_have_no_operational_imports():
    import ast
    from pathlib import Path

    root = Path(__file__).parents[1]
    assert "quality_dips_selected_paper" not in (root / "backend/app/main.py").read_text(encoding="utf-8")
    for relative in ["investment/quality_dips_candidate_evidence.py", "investment/quality_dips_selected_account.py", "api/quality_dips_selected_paper.py"]:
        tree = ast.parse((root / "backend/app" / relative).read_text(encoding="utf-8"))
        imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        assert not any(name.endswith(("quality_dip_scanner", "quality_dip_quotes", "quality_dips_paper", "main")) for name in imports)


def test_supported_instrument_without_fractional_rules_refuses_fraction(tmp_path):
    s = system(tmp_path, fractional=False)
    request = s.approve(s.entry())
    with pytest.raises(ValueError, match="FRACTIONAL_EXECUTION_UNSUPPORTED"):
        s.service.execute(request)
    assert not s.store.trust.current()["entries"]


def test_precision_losing_exit_does_not_publish_intent(tmp_path):
    s = system(tmp_path)
    s.service.execute(s.approve(s.entry()))
    before = {p.name: p.read_bytes() for p in s.store.output.root.iterdir()}
    request = s.approve(s.exit_request("0.00000000000000000000000000001"))
    with pytest.raises(ValueError, match="ARITHMETIC_PRECISION_UNSUPPORTED"):
        s.service.execute(request)
    assert before == {p.name: p.read_bytes() for p in s.store.output.root.iterdir()}


@pytest.mark.parametrize("boundary", ["before-intent", "during-record", "after-commit", "after-ack", "after-pin"])
def test_abrupt_subprocess_crash_preserves_unknown_and_never_replays(tmp_path, boundary):
    import os
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).parents[1]
    env = {**os.environ, "PYTHONPATH": str(root / "backend"), "PYTHONDONTWRITEBYTECODE": "1"}
    process = subprocess.Popen([sys.executable, "-B", str(root / "tests/qd_integration_crash_child.py"), str(tmp_path), boundary],
                               cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, error = process.communicate(timeout=20)
    assert process.returncode == 29, (out, error)
    manifest, _, stamp = bundle_for()
    admission = Admission(tmp_path / "admission.json")
    store, _, _ = fs_bundle(tmp_path, manifest, lambda: stamp, provision=False)
    assert admission.has_unresolved()
    if boundary in ("during-record", "after-commit", "after-ack"):
        with pytest.raises((ValueError, KeyError)): store.snapshot()
    else:
        assert store.snapshot()["state"]["revision"] == (1 if boundary == "after-pin" else 0)
    before = {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    service = SelectedAccountDispatcher(manifest=manifest, owner={"run_id": "fixture-run"}, evidence=None,
        admission=admission, manual=None, publisher=None, projection=None, clock=lambda: stamp)
    assert service.execute({"operation_id": "different-after-crash"})["status"] == "UNKNOWN"
    assert before == {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


@pytest.mark.parametrize("damage", ["forged-proof", "changed-score", "changed-rank", "expired-approval", "scope", "clock", "closed-admission"])
def test_exact_decision_context_and_scope_are_required(tmp_path, damage):
    s = system(tmp_path)
    request = s.approve(s.entry())
    if damage in ("forged-proof", "changed-score", "changed-rank"):
        candidate = strict(request["candidate"])
        if damage == "forged-proof": candidate["ranking_proof"]["verified"] = False
        if damage == "changed-score": candidate["score"] = 999
        if damage == "changed-rank": candidate["ranking"]["rank"] = 0
        request["candidate"] = body(candidate)
    if damage == "expired-approval":
        original = s.manual.verify_and_reserve
        def expired(*args, **kwargs):
            return {**original(*args, **kwargs), "expires_at": s.now[0]}
        s.manual.verify_and_reserve = expired
    if damage == "scope": s.publisher.scope_verifier = lambda *args: False
    if damage == "clock": s.now[0] += 16
    if damage == "closed-admission":
        value = s.admission.load()
        value["closed"] = True
        s.admission.save(value)
    with pytest.raises(ValueError): s.service.execute(request)
    assert not s.store.trust.current()["entries"]


def test_clock_change_after_durable_prepare_preserves_unknown(tmp_path):
    s = system(tmp_path)
    request = s.approve(s.entry())
    prepare = s.admission.prepare
    def clock_change(*args):
        prepare(*args)
        s.now[0] += 1
    s.admission.prepare = clock_change
    assert s.service.execute(request)["status"] == "UNKNOWN"
    assert not s.store.trust.current()["entries"]
    assert s.admission.has_unresolved()


def test_post_factory_uses_only_explicit_disposable_dispatcher(tmp_path):
    s = system(tmp_path)
    router = create_router(reader=s.reader, verifier=s.ReadVerifier(), clock=lambda: s.now[0],
        account_id=s.service.account, epoch=s.service.epoch, commands=s.service)
    assert router.routes[1].endpoint(s.approve(s.entry()))["status"] == "ACKNOWLEDGED"
    assert router.routes[0].endpoint()["cash"] == "900.0"


def test_capacity_refusal_never_creates_financial_intent(tmp_path):
    s = system(tmp_path)
    oversized = s.entry()
    oversized["candidate"] = "x" * 50000
    with pytest.raises(ValueError, match="COMMAND_CAPACITY"):
        s.service.execute(oversized)
    assert not s.store.trust.current()["entries"]


def test_price_moving_above_frozen_reached_level_is_not_entry_eligibility(tmp_path):
    s = system(tmp_path)
    b = copy.deepcopy(s.bundle)
    b["quote"]["execution_price"] = "41"
    s.ranking.current = digest(b)
    s.execution.allowed.add(digest({"instrument": b["instrument"], "quote": b["quote"]}))
    with pytest.raises(ValueError, match="CURRENT_PRICE_ABOVE_LEVEL"):
        s.evidence.candidate(b, level="L1", now=s.now[0])
    assert not s.store.trust.current()["entries"]


@pytest.mark.parametrize("damage", ["missing-cohort", "missing-clock", "missing-gates", "future-observation", "duplicate-level"])
def test_incomplete_source_contract_is_not_eligible(tmp_path, damage):
    s = system(tmp_path)
    b = copy.deepcopy(s.bundle)
    if damage == "missing-cohort": b["publication"].pop("cohort_id")
    if damage == "missing-clock": b["observation"].pop("timestamp")
    if damage == "missing-gates": b["board"][0].pop("missing_critical")
    if damage == "future-observation": b["observation"]["timestamp"] = s.now[0] + 1
    if damage == "duplicate-level":
        # Preserve raw V3/observation equality; duplicate level still refuses.
        b["observation"]["prediction"]["entry_ladder"]["levels"].append({"level": "L1", "reached": True, "limit_price": 40})
    s.ranking.current = digest(b)
    with pytest.raises((ValueError, KeyError)): s.evidence.candidate(b, level="L1", now=s.now[0])
    assert not s.store.trust.current()["entries"]


def test_exit_approval_binds_execution_rule_revision(tmp_path):
    s = system(tmp_path)
    s.service.execute(s.approve(s.entry()))
    request = s.approve(s.exit_request("1"))
    request["instrument"]["rules_revision"] = "substituted-rule-r2"
    s.execution.allowed.add(digest({"instrument": request["instrument"], "quote": request["quote"]}))
    with pytest.raises(ValueError, match="APPROVAL_REFUSED"):
        s.service.execute(request)
    assert len(s.store.trust.current()["entries"]) == 1


@pytest.mark.parametrize("message,expected", [("ONE_POSITION_NO_SCALE_IN", "ONE_POSITION_NO_SCALE_IN"),
    ("private path or credential must not appear in HTTP", "EVIDENCE_UNAVAILABLE")])
def test_post_refusal_exposes_only_safe_reason_codes(tmp_path, message, expected):
    from fastapi import HTTPException

    s = system(tmp_path)
    def refuse(request):
        raise ValueError(message)
    router = create_router(reader=s.reader, verifier=s.ReadVerifier(), clock=lambda: s.now[0],
        account_id=s.service.account, epoch=s.service.epoch, commands=SimpleNamespace(execute=refuse))
    with pytest.raises(HTTPException) as error:
        router.routes[1].endpoint({})
    assert error.value.detail == {"code": "COMMAND_REFUSED", "reason": expected}


def test_existing_board_ranking_and_v3_plan_feed_the_complete_chain(tmp_path):
    from app.investment.board import build_quality_dips_board
    from app.investment.quality_dips_v3 import build_v3_entry_plan

    s = system(tmp_path, "SPY", "ETF")
    research = {"symbol": "SPY", "asset_type": "ETF", "classification": "ACCUMULATION", "thesis": "INTACT",
                "evidence_quality": "HIGH", "missing_critical": [], "opportunity_score": 87.5,
                "components": {"valuation": 75, "fundamentals": 82, "drawdown": 80, "thesis_integrity": 90},
                "timestamp": datetime.fromtimestamp(s.now[0], UTC).isoformat(), "price": 40.0}
    board = build_quality_dips_board([research, {**research, "symbol": "AAPL", "asset_type": "STOCK", "opportunity_score": 95}])
    plan = build_v3_entry_plan(symbol="SPY", current_price=40, normalization={"conservative": 45, "base": 50, "optimistic": 55},
        quality_score=82, fundamentals_score=80, valuation_score=72, drawdown_percentile=80, evidence_quality="HIGH",
        thesis_intact=True, value_trap=False)
    row = next(row for row in board if row["symbol"] == "SPY")
    row["quality_dips_v2"] = {"quality_dips_v3": plan}
    s.bundle["board"] = board
    s.bundle["observation"].update(prediction=plan, classification=plan["patient_state"])
    s.ranking.replace(s.bundle)
    original = body(board)
    request = s.approve(s.entry())
    frozen = strict(request["candidate"])
    assert frozen["ranking"]["rank"] == next(i + 1 for i, row in enumerate(board) if row["symbol"] == "SPY")
    assert s.service.execute(request)["status"] == "ACKNOWLEDGED"
    assert s.read()["cash"] == "900.0" and body(board) == original


def test_conflicting_acknowledged_operation_is_refused_not_reapplied(tmp_path):
    s = system(tmp_path)
    request = s.approve(s.entry())
    s.service.execute(request)
    altered = {**request, "quantity": "1"}
    with pytest.raises(ValueError, match="OPERATION_ID_CONFLICT"):
        s.service.execute(altered)
    assert len(s.store.trust.current()["entries"]) == 1


def test_lost_prior_projection_verification_latches_all_new_operations(tmp_path):
    s = system(tmp_path)
    request = s.approve(s.entry())
    s.service.execute(request)
    s.projection.verify = lambda receipt: False
    assert s.service.execute(request)["status"] == "UNKNOWN"
    assert s.admission.has_unresolved()
    assert s.dispatcher().execute({"operation_id": "another"})["status"] == "UNKNOWN"
    assert len(s.store.trust.current()["entries"]) == 1


def test_ambiguous_admission_state_is_durably_unknown(tmp_path):
    s = system(tmp_path)
    request = s.approve(s.entry())
    s.admission.has_unresolved = lambda: None
    assert s.service.execute(request)["status"] == "UNKNOWN"
    assert s.admission.lookup("entry", digest(request))["status"] == "UNKNOWN"
    assert not s.store.trust.current()["entries"]


@pytest.mark.parametrize("damage", ["receipt", "unavailable"])
def test_corrupt_prior_acknowledgement_blocks_future_effects(tmp_path, damage):
    s = system(tmp_path)
    request = s.approve(s.entry())
    s.service.execute(request)
    if damage == "receipt":
        row = s.admission.lookup("entry", digest(request))
        row["receipt"] = None
        s.admission.finish("entry", row)
    else:
        def unavailable(receipt): raise OSError("fixture projection unavailable")
        s.projection.verify = unavailable
    assert s.service.execute(request)["status"] == "UNKNOWN"
    assert s.admission.has_unresolved()


def test_failure_to_persist_unknown_marker_is_not_claimed_durable(tmp_path):
    s = system(tmp_path)
    request = s.approve(s.entry())
    def fail(*args, **kwargs): raise OSError("fixture storage full")
    s.publisher.execute = fail
    s.admission.mark_unknown = fail
    result = s.service.execute(request)
    assert result["status"] == "UNKNOWN" and result["durable_refusal_recorded"] is False
    assert s.admission.lookup("entry", digest(request))["status"] == "PENDING"
    assert not s.store.trust.current()["entries"]
