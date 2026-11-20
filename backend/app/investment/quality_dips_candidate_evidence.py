"""Inert source-shaped adapter. Injected verifiers are a trust boundary, not an issuer.

No scanner/provider imports, financial mirror, default paths or mutable singleton.
JSON strings freeze evidence; hashes bind content but never authenticate it.
"""
from datetime import datetime

from app.services.paper_financial_replay import body, digest, number, strict, text
from app.services.quality_dips_account_policy import verify_reached_level


def timestamp(value):
    if type(value) is int:
        return value
    if type(value) is not str:
        raise ValueError("SOURCE_TIME_MISSING")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.microsecond:
        raise ValueError("SOURCE_TIME_AMBIGUOUS")
    return int(parsed.timestamp())


def verified(result, binding, schema):
    if (type(result) is not dict or result.get("schema") != schema or result.get("verified") is not True
            or result.get("binding") != binding):
        raise ValueError("AUTHORITY_UNVERIFIED")
    text(result["receipt_id"])
    return strict(body(result))


class CandidateEvidenceAdapter:
    def __init__(self, *, ranking_authority, execution_authority):
        self.ranking_authority = ranking_authority
        self.execution_authority = execution_authority

    def execution(self, instrument, quote, *, now):
        # No conversion of registry tradable flags or binary floats to fill facts.
        if (type(now) is not int or type(instrument) is not dict or type(quote) is not dict
                or instrument.get("asset_class") not in ("STOCK", "ETF")
                or instrument.get("currency") != "USD" or instrument.get("units") != "SHARES"
                or instrument.get("long_supported") is not True or type(instrument.get("fractional")) is not bool
                or quote.get("symbol") != instrument.get("symbol")
                or quote.get("instrument_id") != instrument.get("instrument_id")
                or not 0 <= now - timestamp(quote.get("effective_timestamp")) <= 30
                or number(quote.get("execution_price")) <= 0):
            raise ValueError("EXECUTION_EVIDENCE_INVALID")
        for key in ("instrument_id", "symbol", "rules_revision"):
            text(instrument[key])
        text(quote["source"])
        evidence = {"instrument": instrument, "quote": quote}
        proof = verified(self.execution_authority.verify(evidence, now=now), digest(evidence), "QD_EXECUTION_VERIFIED_V1")
        return {"instrument": strict(body(instrument)), "quote": {"symbol": quote["symbol"],
                "price": quote["execution_price"], "observed_at": timestamp(quote["effective_timestamp"]),
                "source_id": quote["source"]}, "source_quote": strict(body(quote)), "execution_proof": proof}

    def candidate(self, bundle, *, level, now):
        frozen = body(bundle)
        if len(frozen.encode()) > 16384:
            raise ValueError("CANDIDATE_CAPACITY")
        bundle = strict(frozen)
        pub, observation = bundle["publication"], bundle["observation"]
        board, instrument = bundle["board"], bundle["instrument"]
        if (type(board) is not list or not board or len(board) > 100
                or any(type(row) is not dict for row in board)
                or len({row.get("symbol") for row in board}) != len(board)
                or pub.get("schema") != "QD_RANKING_REVISION_V1" or pub.get("state") != "ACTIVE"
                or type(pub.get("generation")) is not int or pub["generation"] < 1
                or type(pub.get("source_revision")) is not int or pub["source_revision"] < 1
                or type(pub.get("issued_at")) is not int or type(pub.get("expires_at")) is not int
                or not 0 <= now - pub["issued_at"] <= 600 or not pub["issued_at"] <= now < pub["expires_at"]
                or pub["expires_at"] - pub["issued_at"] > 600):
            raise ValueError("RANKING_NOT_CURRENT")
        text(pub["issuer"])
        text(pub["cohort_id"])
        proof = verified(self.ranking_authority.verify_current(bundle, now=now), digest(bundle), "QD_RANKING_VERIFIED_V1")
        execution = self.execution(instrument, bundle["quote"], now=now)
        symbol = instrument["symbol"]
        matches = [(index, row) for index, row in enumerate(board) if row["symbol"] == symbol]
        if len(matches) != 1:
            raise ValueError("CANDIDATE_NOT_RANKED")
        index, row = matches[0]
        v3 = (row.get("quality_dips_v2") or {}).get("quality_dips_v3") or {}
        ladder = (observation.get("prediction") or {}).get("entry_ladder") or {}
        levels = [item["level"] for item in ladder.get("levels", []) if item.get("reached") is True]
        if (observation.get("symbol") != symbol or observation.get("strategy_version") != "QUALITY_DIPS_V3"
                or observation.get("policy_version") != "quality-dips-v3-mos-15-20-25-30-v1"
                or observation.get("evidence_class") != "FORWARD_COLLECTION"
                or observation.get("execution") != "MANUAL_ONLY" or type(observation.get("missing_data")) is not list
                or observation["missing_data"]
                or observation.get("classification") not in ("ACCUMULATION", "DEEP_VALUE", "GENERATIONAL")
                or v3.get("patient_state") != observation["classification"] or type(v3.get("blockers")) is not list or v3["blockers"]
                or v3.get("entry_ladder") != ladder or ladder.get("ready") is not True
                or level not in ("L1", "L2", "L3", "L4") or level not in levels
                or type(row.get("blockers")) is not list or row["blockers"]
                or type(row.get("missing_critical")) is not list or row["missing_critical"]
                or row.get("asset_type") not in (instrument["asset_class"], "SECTOR_ETF")
                or (row.get("asset_type") == "SECTOR_ETF" and instrument["asset_class"] != "ETF")
                or not 0 <= now - timestamp(observation.get("source_timestamp")) <= 600
                or not timestamp(observation["source_timestamp"]) <= timestamp(observation.get("timestamp")) <= pub["issued_at"]):
            raise ValueError("OBSERVATION_NOT_ELIGIBLE")
        verify_reached_level(ladder, level, execution["quote"]["price"])
        reasons = row.get("reasons")
        if type(reasons) is not list or not reasons or any(type(reason) is not str for reason in reasons):
            raise ValueError("RESEARCH_REASONS_MISSING")
        score = row.get("opportunity_score")
        if type(score) not in (str, int, float) or not number(str(score)).is_finite():
            raise ValueError("RESEARCH_SCORE_MISSING")
        ranking = {"symbol": symbol, "instrument_id": instrument["instrument_id"],
                   "observation_id": text(observation["observation_id"]), "level": level, "rank": index + 1,
                   "ranked_at": pub["issued_at"], "source_id": pub["issuer"], "revision": pub["source_revision"],
                   "strategy_version": observation["strategy_version"], "policy_version": observation["policy_version"],
                   "evidence_class": observation["evidence_class"], "classification": observation["classification"],
                   "reached_levels": levels}
        result = body({"schema": "QD_CANDIDATE_EVIDENCE_V1", "source_bundle": bundle, "ranking": ranking,
                     "generation": pub["generation"], "source_revision": pub["source_revision"],
                     "cohort_id": pub["cohort_id"],
                     "expires_at": pub["expires_at"], "reasons": reasons, "score": score,
                     "execution": execution, "ranking_proof": proof})
        if len(result.encode()) > 32768:
            raise ValueError("CANDIDATE_CAPACITY")
        return result
