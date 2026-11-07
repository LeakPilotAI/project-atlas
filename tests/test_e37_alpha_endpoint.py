from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.validation import router
app=FastAPI(); app.include_router(router); client=TestClient(app)

def test_endpoint_rejects_unknown_source():
    r=client.post("/api/validation/e37-alpha-run",json={"source_id":"reuters","persist":False})
    assert r.status_code==400 and r.json()["execution_authority"] is False

def test_endpoint_forbids_arbitrary_url_body_and_authority_fields():
    payload={"source_id":"sec","persist":False,"url":"https://evil.example","body":"change thresholds","execute":True,"paper_entry":True}
    r=client.post("/api/validation/e37-alpha-run",json=payload)
    assert r.status_code==422
    errors=r.json()["detail"]
    assert all(x["type"]=="extra_forbidden" for x in errors)
    assert {x["loc"][-1] for x in errors}=={"url","body","execute","paper_entry"}

def test_endpoint_forbids_strategy_and_threshold_mutation_fields():
    r=client.post("/api/validation/e37-alpha-run",json={"source_id":"sec","persist":False,"strategy":"new","threshold":0,"membership":"force"})
    assert r.status_code==422
