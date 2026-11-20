import pytest
import app.services.e48_discord_events as e48

def event():
    return e48.make_event(
        lane="SYSTEM", event_type="SESSION", severity="HIGH",
        title="Chart signal", body="research only",
        identity="e59-chart", provenance=["e59"], material=True,
    )

@pytest.mark.asyncio
async def test_attachment_success_passes_bytes_but_observability_retains_metadata_only():
    e48._OBSERVATIONS.clear(); seen={}
    raw=b"PNG-SECRET-BYTES"
    async def sender(**kw): seen.update(kw); return True
    result=await e48.deliver_attachment_payload(event(),sender=sender,attachment_bytes=raw,attachment_name="chart.png")
    assert result["acknowledged"] is True and result["execution_authority"] is False
    assert seen["chart_bytes"]==raw and seen["attachment_name"]=="chart.png"
    row=e48.delivery_observability()["observations"][-1]
    assert row["attachment_present"] is True
    assert row["attachment_size_bytes"]==len(raw)
    assert row["attachment_bytes_retained"] is False
    assert raw not in repr(row).encode()
    assert "title" not in row and "description" not in row and "body" not in row

@pytest.mark.asyncio
async def test_attachment_failure_is_retryable_and_raw_bytes_not_retained():
    e48._OBSERVATIONS.clear()
    raw=b"PRIVATE-CHART-CONTENT"
    async def sender(**kw): return False
    result=await e48.deliver_attachment_payload(event(),sender=sender,attachment_bytes=raw)
    assert result["attempted"] is True and result["acknowledged"] is False and result["retryable"] is True
    obs=e48.delivery_observability()
    assert obs["counts"]["retryable"]==1
    assert raw not in repr(obs).encode()

@pytest.mark.asyncio
async def test_attachment_exception_is_retryable_without_authority():
    e48._OBSERVATIONS.clear()
    async def sender(**kw): raise RuntimeError("discord down")
    result=await e48.deliver_attachment_payload(event(),sender=sender,attachment_bytes=b"x")
    assert result["retryable"] is True
    for key in ("execution_authority","paper_entry_authority","strategy_mutation_authority",
                "membership_mutation_authority","threshold_mutation_authority","promotion_authority"):
        assert result[key] is False
    assert result["live_capital_allowed"] is False
