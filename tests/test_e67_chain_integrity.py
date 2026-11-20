import json
from app.investment.quality_dips_crypto_store import CryptoProspectiveEvidenceStore

def row(symbol,day):
    return {"asset_class":"CRYPTO","symbol":symbol,"observed_at":f"2026-10-{day}T12:00:00+00:00","evidence":{},"evidence_valid":True}

def test_new_rows_are_chained_and_reload_verified(tmp_path):
    path=tmp_path/"e.jsonl"; store=CryptoProspectiveEvidenceStore(path)
    assert store.append(row("BTC","06")); assert store.append(row("ETH","07"))
    assert store.records[0]["chain_sequence"]==1 and store.records[0]["previous_chain_hash"]=="GENESIS"
    assert store.records[1]["chain_sequence"]==2 and store.records[1]["previous_chain_hash"]==store.records[0]["chain_hash"]
    loaded=CryptoProspectiveEvidenceStore(path)
    assert loaded.integrity["ok"] is True and loaded.integrity["chain_verified_lines"]==2

def test_reordered_chain_fails_closed(tmp_path):
    path=tmp_path/"e.jsonl"; store=CryptoProspectiveEvidenceStore(path)
    store.append(row("BTC","06")); store.append(row("ETH","07"))
    lines=path.read_text(encoding="utf-8").splitlines(); path.write_text("\n".join(reversed(lines))+"\n",encoding="utf-8")
    loaded=CryptoProspectiveEvidenceStore(path)
    assert loaded.integrity["ok"] is False and loaded.integrity["chain_mismatch_lines"]>0
    try: loaded.append(row("SOL","08")); assert False
    except ValueError: pass

def test_removed_non_tail_record_fails_chain(tmp_path):
    path=tmp_path/"e.jsonl"; store=CryptoProspectiveEvidenceStore(path)
    store.append(row("BTC","06")); store.append(row("ETH","07")); store.append(row("SOL","08"))
    lines=path.read_text(encoding="utf-8").splitlines(); path.write_text(lines[0]+"\n"+lines[2]+"\n",encoding="utf-8")
    loaded=CryptoProspectiveEvidenceStore(path)
    assert loaded.integrity["ok"] is False and loaded.integrity["chain_mismatch_lines"]==1

def test_legacy_rows_are_explicitly_unverified_not_chain_verified(tmp_path):
    path=tmp_path/"e.jsonl"; legacy=row("BTC","05")
    from app.investment.quality_dips_crypto_store import observation_identity
    legacy["observation_id"]=observation_identity(legacy)
    path.write_text(json.dumps(legacy)+"\n",encoding="utf-8")
    loaded=CryptoProspectiveEvidenceStore(path)
    assert loaded.integrity["ok"] is True
    assert loaded.integrity["legacy_unverified_lines"]==1 and loaded.integrity["chain_verified_lines"]==0

def test_tail_truncation_detected_by_chain_head(tmp_path):
    path=tmp_path/"e.jsonl"; store=CryptoProspectiveEvidenceStore(path)
    store.append(row("BTC","06")); store.append(row("ETH","07"))
    lines=path.read_text(encoding="utf-8").splitlines(); path.write_text(lines[0]+"\n",encoding="utf-8")
    loaded=CryptoProspectiveEvidenceStore(path)
    assert loaded.integrity["ok"] is False and loaded.integrity["chain_anchor_mismatch"] is True
    try: loaded.append(row("SOL","08")); assert False
    except ValueError: pass
