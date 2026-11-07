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

@pytest.mark.asyncio
async def test_native_capacity_changes_after_real_disposable_orders_and_stops(system):
    """Guarded native real-write capacity accounting, not full F11 saturation."""
    s = system
    before = {
        'global': s.journal.remaining_slots(),
        'qd': s.q.writer.store.remaining_operations(),
        'perp': s.p.writer.store.remaining_operations(),
        'orders': s.p.orders.remaining_slots(),
    }
    await native_fixtures.cycle(s)
    after = {
        'global': s.journal.remaining_slots(),
        'qd': s.q.writer.store.remaining_operations(),
        'perp': s.p.writer.store.remaining_operations(),
        'orders': s.p.orders.remaining_slots(),
    }
    assert after['global'] < before['global']
    assert after['qd'] < before['qd']
    assert after['orders'] < before['orders']
    assert after['perp'] == before['perp']
    assert all(value >= 0 for value in after.values())
    stopped = s.r.stop()
    assert stopped['state'] == 'STOPPED'
    assert s.journal.snapshot()['state']['finalized'] is not None
    assert s.journal.remaining_slots() < after['global']
    assert s.p.orders.remaining_slots() <= after['orders']
    assert s.r.stop() == stopped

@pytest.mark.asyncio
async def test_native_real_write_headroom_refuses_unfunded_followup_envelope(system):
    """Guarded actual native write plus fail-closed workload forecast, not F11 saturation."""
    from app.services.paper_capacity_envelope import assess_multi_store_envelope
    s = system
    await native_fixtures.cycle(s)
    actual = {
        'GLOBAL': s.journal.remaining_slots(),
        'QUALITY_DIPS': s.q.writer.store.remaining_operations(),
        'HYPERLIQUID': s.p.writer.store.remaining_operations(),
        'PERP_ORDERS': s.p.orders.remaining_slots(),
        'REPORTS': s.qstop.reports.archive.remaining_reports(),
    }
    assert all(0 <= count <= 128 for count in actual.values())
    # Forecast a workload that exactly consumes the currently observed free
    # slots of one store; the mandatory stop reserve must veto that forecast.
    stores = {name: {'capacity': 128, 'used': 128 - count,
                     'planned': 0, 'shutdown_reserve': 1}
              for name, count in actual.items()}
    stores['GLOBAL']['planned'] = actual['GLOBAL']
    result = assess_multi_store_envelope(stores)
    assert result['fits_declared_envelope'] is False
    assert result['stores']['GLOBAL']['required'] > result['stores']['GLOBAL']['remaining']
    assert result['operational_admission'] is False
    stopped = s.r.stop()
    assert stopped['state'] == 'STOPPED'
    assert s.journal.snapshot()['state']['finalized'] is not None

@pytest.mark.asyncio
async def test_native_repeated_observations_do_not_spend_shutdown_reserve(system):
    """Guarded native bounded observations, with real writers and no mock headroom."""
    s = system
    await native_fixtures.cycle(s)
    initial = (s.journal.remaining_slots(),
               s.q.writer.store.remaining_operations(),
               s.p.writer.store.remaining_operations(),
               s.p.orders.remaining_slots())
    # Repeatedly observe unchanged synthetic market data; neither duplicate
    # entry nor duplicate resting-order reservation may consume stop capacity.
    for _ in range(12):
        await native_fixtures.cycle(s)
    final = (s.journal.remaining_slots(),
             s.q.writer.store.remaining_operations(),
             s.p.writer.store.remaining_operations(),
             s.p.orders.remaining_slots())
    assert final == initial
    assert len(s.p.orders.snapshot()['state']['orders']) == 1
    assert s.q.writer._cut()['state']['revision'] == 1
    stopped = s.r.stop()
    assert stopped['state'] == 'STOPPED'
    assert s.journal.snapshot()['state']['finalized'] is not None
    assert s.r.stop() == stopped
