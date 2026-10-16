import csv,json
from pathlib import Path
from app.backtest.provider_normalize import merge_context_exports,normalize_oi_export


def _csv(path:Path,fields,rows):
    with path.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(rows)


def test_provider_exports_merge_into_pit_context(tmp_path:Path):
    oi=tmp_path/"oi.json";vol=tmp_path/"vol.csv";htf=tmp_path/"htf.jsonl";out=tmp_path/"context.csv"
    oi.write_text(json.dumps({"data":[{"time":1767225600000,"openInterest":80000},{"time":1767225900000,"openInterest":81000}]}),encoding="utf-8")
    _csv(vol,["timestamp","volume_24h_usd"],[{"timestamp":"2026-01-01T00:00:00Z","volume_24h_usd":200000},{"timestamp":"2026-01-01T00:05:00Z","volume_24h_usd":201000}])
    htf.write_text('\n'.join([json.dumps({"ts":1767225600000,"aligned":True}),json.dumps({"ts":1767225900000,"aligned":False})])+'\n',encoding="utf-8")
    merge_context_exports(oi_path=oi,volume_path=vol,htf_path=htf,output_path=out)
    rows=list(csv.DictReader(out.open("r",encoding="utf-8")))
    assert len(rows)==2;assert rows[0]["open_interest_usd"]=="80000.0";assert rows[1]["htf_regime_aligned"]=="false"


def test_unmatched_timestamps_fail_closed(tmp_path:Path):
    oi=tmp_path/"oi.csv";vol=tmp_path/"vol.csv";htf=tmp_path/"htf.csv"
    _csv(oi,["timestamp","oi_usd"],[{"timestamp":"2026-01-01T00:00:00Z","oi_usd":80000}])
    _csv(vol,["timestamp","volume_usd"],[{"timestamp":"2026-01-01T00:05:00Z","volume_usd":200000}])
    _csv(htf,["timestamp","aligned"],[{"timestamp":"2026-01-01T00:00:00Z","aligned":"true"}])
    try:merge_context_exports(oi_path=oi,volume_path=vol,htf_path=htf,output_path=tmp_path/"out.csv")
    except ValueError as e:assert "not perfectly aligned" in str(e)
    else:raise AssertionError("unmatched provider timestamps must fail closed")


def test_duplicate_or_negative_oi_fails_closed(tmp_path:Path):
    p=tmp_path/"oi.csv"
    _csv(p,["timestamp","open_interest_usd"],[{"timestamp":"2026-01-01T00:00:00Z","open_interest_usd":-1}])
    try:normalize_oi_export(p)
    except ValueError as e:assert "negative OI" in str(e)
    else:raise AssertionError("negative historical OI must fail closed")
