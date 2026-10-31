from fastapi.testclient import TestClient
from app.main import app
import app.services.e48_discord_events as e48

client=TestClient(app)

def test_e53_get_only_observability_endpoint_is_payload_free():
    e48._OBSERVATIONS.clear()
    e48._OBSERVATIONS.append({"observed_at":"x","event_id":"id","lane":"SYSTEM","event_type":"SESSION",
        "severity":"INFO","eligible":True,"attempted":True,"acknowledged":True,"deduped":False,
        "retryable":False,"destination":"DISCORD_DM","external_text_inert":True})
    r=client.get("/api/observability/discord-delivery")
    assert r.status_code==200
    data=r.json()
    assert data["read_only"] is True and data["live_capital_allowed"] is False
    assert data["execution_authority"] is False and data["paper_entry_authority"] is False
    assert data["threshold_mutation_authority"] is False and data["promotion_authority"] is False
    blob=str(data).lower()
    assert "description" not in blob and "'body'" not in blob and "'title'" not in blob

def test_e53_observability_endpoint_has_no_write_methods():
    for method in ("post","put","patch","delete"):
        r=getattr(client,method)("/api/observability/discord-delivery")
        assert r.status_code==405

def test_e53_observability_is_bounded():
    e48._OBSERVATIONS.clear()
    for i in range(250):
        e48._OBSERVATIONS.append({"observed_at":"x","event_id":str(i),"lane":"SYSTEM","event_type":"SESSION",
            "severity":"INFO","eligible":True,"attempted":True,"acknowledged":True,"deduped":False,
            "retryable":False,"destination":"DISCORD_DM","external_text_inert":True})
    data=client.get("/api/observability/discord-delivery").json()
    assert data["retention_limit"]==200 and data["counts"]["total"]==200 and len(data["observations"])==200
