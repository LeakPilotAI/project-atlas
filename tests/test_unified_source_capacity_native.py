"""Actual native accounts: capacity refusal occurs before global/financial effects."""
import pytest
import test_unified_actual_native_lanes as native_fixtures

system=native_fixtures.system


@pytest.mark.asyncio
@pytest.mark.parametrize('lane',['QUALITY_DIPS','HYPERLIQUID'])
async def test_global_capacity_retains_native_shutdown_slots(system,monkeypatch,lane):
    s=system
    await s.r.poll()
    proposal=await s.r.lanes[lane].next_proposal(s.r.observations[lane])
    old=s.journal.snapshot(); q=s.q.writer._cut(); p=s.p.writer._cut()
    monkeypatch.setattr(s.journal,'remaining_slots',lambda:3)
    with pytest.raises(ValueError,match='CAPACITY'):
        if lane=='QUALITY_DIPS':s.r.dispatch(lane,proposal)
        else:s.r.admit_resting(proposal)
    assert s.journal.snapshot()==old and s.q.writer._cut()==q and s.p.writer._cut()==p
    assert not s.r.uncertain


@pytest.mark.asyncio
async def test_order_journal_keeps_resolution_capacity(system,monkeypatch):
    s=system
    await s.r.poll()
    monkeypatch.setattr(s.p.orders,'remaining_slots',lambda:2)
    before=s.p.orders.snapshot()
    with pytest.raises(ValueError,match='CAPACITY'):
        await s.plane.next_proposal(s.r.observations['HYPERLIQUID'])
    assert s.p.orders.snapshot()==before and s.p.writer._cut()['state']['revision']==0


@pytest.mark.asyncio
async def test_continuous_run_uses_reserved_capacity_for_verified_final_and_never_resets(system,monkeypatch):
    s=system
    monkeypatch.setattr(s.journal,'remaining_slots',lambda:3)
    result=await s.r.run(seconds=.2,interval=.05)
    assert result['state']=='STOPPED'
    assert s.journal.snapshot()['state']['finalized']
    assert s.q.writer._cut()['state']['revision']==0 and s.p.writer._cut()['state']['revision']==0
    s.a.verify_session=lambda *args:True
    monkeypatch.setattr(s.journal,'remaining_slots',lambda:2)
    before=s.journal.snapshot()
    assert not s.custody.verify_restart({'session_id':'new-synthetic-session'})
    assert s.journal.snapshot()==before


@pytest.mark.asyncio
@pytest.mark.parametrize('lane',['QUALITY_DIPS','HYPERLIQUID'])
async def test_native_financial_headroom_refuses_before_global_reservation(system,monkeypatch,lane):
    s=system
    await s.r.poll();proposal=await s.r.lanes[lane].next_proposal(s.r.observations[lane])
    monkeypatch.setattr(s.writers[lane].store,'remaining_operations',lambda:1)
    before=s.journal.snapshot()
    with pytest.raises(ValueError,match='FINANCIAL_CAPACITY'):
        if lane=='QUALITY_DIPS':s.r.dispatch(lane,proposal)
        else:s.r.admit_resting(proposal)
    assert s.journal.snapshot()==before and not s.r.uncertain
    assert s.writers[lane]._cut()['state']['revision']==0


@pytest.mark.asyncio
async def test_report_headroom_is_read_only_and_triggers_existing_safe_stop(system,monkeypatch):
    s=system
    monkeypatch.setattr(s.qstop.reports.archive,'remaining_reports',lambda:3)
    outcome=await s.r.run(seconds=.2,interval=.05)
    assert outcome['state']=='STOPPED' and s.journal.snapshot()['state']['finalized']
    assert s.q.writer._cut()['state']['revision']==0

@pytest.mark.asyncio
async def test_native_store_capacity_readbacks_are_consistent_without_mocked_headroom(system):
    """Guarded native source check; F11 exhaustion remains separately pending."""
    s = system
    stores = {
        'GLOBAL': s.journal.remaining_slots(),
        'QUALITY_DIPS': s.writers['QUALITY_DIPS'].store.remaining_operations(),
        'HYPERLIQUID': s.writers['HYPERLIQUID'].store.remaining_operations(),
        'PERP_ORDERS': s.p.orders.remaining_slots(),
        'REPORTS': s.qstop.reports.archive.remaining_reports(),
    }
    assert set(stores) == {'GLOBAL', 'QUALITY_DIPS', 'HYPERLIQUID', 'PERP_ORDERS', 'REPORTS'}
    assert all(type(count) is int and 0 <= count <= 128 for count in stores.values())
    assert stores == {
        'GLOBAL': s.journal.remaining_slots(),
        'QUALITY_DIPS': s.writers['QUALITY_DIPS'].store.remaining_operations(),
        'HYPERLIQUID': s.writers['HYPERLIQUID'].store.remaining_operations(),
        'PERP_ORDERS': s.p.orders.remaining_slots(),
        'REPORTS': s.qstop.reports.archive.remaining_reports(),
    }
    assert not s.r.uncertain

@pytest.mark.asyncio
async def test_native_capacity_readback_is_side_effect_free_across_all_five_stores(system):
    """Guarded native read-only check; not a saturation or shutdown proof."""
    s = system
    before = (s.journal.snapshot(), s.q.writer._cut(), s.p.writer._cut(),
              s.p.orders.snapshot())
    readers = (
        s.journal.remaining_slots,
        s.q.writer.store.remaining_operations,
        s.p.writer.store.remaining_operations,
        s.p.orders.remaining_slots,
        s.qstop.reports.archive.remaining_reports,
    )
    first = tuple(reader() for reader in readers)
    second = tuple(reader() for reader in readers)
    assert first == second
    assert all(type(value) is int and value >= 0 for value in first)
    assert (s.journal.snapshot(), s.q.writer._cut(), s.p.writer._cut(),
            s.p.orders.snapshot()) == before
