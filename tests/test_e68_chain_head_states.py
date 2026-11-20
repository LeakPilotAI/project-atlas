import json
from app.investment.quality_dips_crypto_store import CryptoProspectiveEvidenceStore, observation_identity

def row(symbol="BTC"):
    return {"asset_class":"CRYPTO","symbol":symbol,"observed_at":"2026-10-06T13:00:00+00:00","evidence":{},"evidence_valid":True}

def test_explicit_chain_states(tmp_path):
    path=tmp_path/"e.jsonl"; assert CryptoProspectiveEvidenceStore(path).integrity["chain_state"]=="NO_CHAIN_YET"
    legacy=row(); legacy["observation_id"]=observation_identity(legacy); path.write_text(json.dumps(legacy)+"\n",encoding="utf-8")
    assert CryptoProspectiveEvidenceStore(path).integrity["chain_state"]=="LEGACY_UNVERIFIED"
    path.unlink(); store=CryptoProspectiveEvidenceStore(path); store.append(row())
    assert CryptoProspectiveEvidenceStore(path).integrity["chain_state"]=="VERIFIED"

def test_missing_anchor_with_chained_rows_is_compromised(tmp_path):
    path=tmp_path/"e.jsonl"; store=CryptoProspectiveEvidenceStore(path); store.append(row()); store.head_path.unlink()
    loaded=CryptoProspectiveEvidenceStore(path)
    assert loaded.integrity["chain_state"]=="COMPROMISED" and loaded.integrity["chain_anchor_mismatch"] is True
    try: loaded.append(row("ETH")); assert False
    except ValueError: pass

def test_malformed_anchor_is_compromised(tmp_path):
    path=tmp_path/"e.jsonl"; store=CryptoProspectiveEvidenceStore(path); store.append(row()); store.head_path.write_text("{bad",encoding="utf-8")
    loaded=CryptoProspectiveEvidenceStore(path)
    assert loaded.integrity["chain_state"]=="COMPROMISED" and loaded.integrity["ok"] is False

def test_stale_anchor_and_interrupted_head_update_fail_closed(tmp_path):
    path=tmp_path/"e.jsonl"; store=CryptoProspectiveEvidenceStore(path); store.append(row()); first=store.head_path.read_text(encoding="utf-8"); store.append(row("ETH"))
    store.head_path.write_text(first,encoding="utf-8")
    loaded=CryptoProspectiveEvidenceStore(path)
    assert loaded.integrity["chain_state"]=="COMPROMISED"
    store.head_path.write_text(json.dumps({"sequence":2,"chain_hash":store.records[-1]["chain_hash"]}),encoding="utf-8")
    store.head_path.unlink(); PathCls=type(store.head_path); PathCls(str(store.head_path)+".tmp").write_text("interrupted",encoding="utf-8")
    interrupted=CryptoProspectiveEvidenceStore(path)
    assert interrupted.integrity["chain_state"]=="COMPROMISED"
