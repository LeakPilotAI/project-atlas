"""Inspect genuine scored Alpaca research receipts for QD native forward intake.

Pure read-only bridge, no provider, account, cursor update, source issuance,
trade, or financial authority. Scored rankings cannot become native signals.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT=Path(r"D:/Work/Project Atlas")
RESEARCH=ROOT/"logs/research"
RECEIPT=re.compile(r"alpaca-scored-([0-9a-f]{64})\.json\Z")
SOURCE_FIELDS=(
    "research_rows_with_original_provenance",
    "current_quality_dips_v3_forward_observations",
    "current_enrolled_stock_etf_instruments",
    "accepted_execution_quote_evidence",
    "current_issuer_signed_ranking_revision",
    "current_native_position_monitors",
    "accepted_native_scanner_publication",
)
SCHEMA="ATLAS_QD_SCORED_RESEARCH_NATIVE_INTAKE_READONLY_V1"


def inspect_receipt(path, *, root=RESEARCH, catalog=None):
    root=Path(root)
    path=Path(path)
    match=RECEIPT.fullmatch(path.name)
    # No symlink or unsafe directory substitution; no path traversal.
    if (path.parent != root or match is None or root.is_symlink()
            or not root.is_dir() or path.is_symlink() or not path.is_file()
            or path.stat().st_size==0 or path.stat().st_size>65536):
        raise ValueError("QD_NATIVE_INTAKE_EXACT_READONLY_RECEIPT_REQUIRED")
    raw=path.read_bytes()
    digest=hashlib.sha256(raw).hexdigest()
    if digest!=match.group(1):
        raise ValueError("QD_NATIVE_INTAKE_RESEARCH_RECEIPT_DIGEST_MISMATCH")
    def unique(pairs):
        out={}
        for key, value in pairs:
            if key in out:
                raise ValueError("QD_NATIVE_INTAKE_DUPLICATE_FIELD")
            out[key]=value
        return out
    try:
        report=json.loads(raw,object_pairs_hook=unique,
                          parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError) as exc:
        raise ValueError("QD_NATIVE_INTAKE_RESEARCH_RECEIPT_MALFORMED") from None
    if (type(report) is not dict or set(report)!={
            "schema","batch","results","scoring_complete",
            "cursor_advanced","paper_execution_authorized","live_order_authorized"}
            or report["schema"]!="ATLAS_BROAD_SCORED_RESEARCH_V1"
            or report["scoring_complete"] is not True
            or report["cursor_advanced"] is not False
            or report["paper_execution_authorized"] is not False
            or report["live_order_authorized"] is not False
            or type(report["batch"]) is not dict
            or report["batch"].get("schema")!="ATLAS_ALPACA_RESEARCH_BATCH_V1"
            or report["batch"].get("hyperliquid_perpetuals_included") is not False
            or report["batch"].get("paper_execution_authorized") is not False
            or report["batch"].get("live_order_authorized") is not False):
        raise ValueError("QD_NATIVE_INTAKE_SCOPED_SCORED_RESEARCH_REQUIRED")
    batch=report["batch"]
    expected=batch.get("symbols")
    rows=report["results"]
    if (type(expected) is not list or type(rows) is not list
            or not 1<=len(rows)==len(expected)<=2
            or len(set(expected))!=len(expected)
            or any(type(s) is not str or re.fullmatch(r"[A-Z][A-Z0-9.-]{0,14}",s) is None
                   for s in expected)
            or any(type(r) is not dict or r.get("symbol")!=sym
                   or r.get("status")!="RESEARCH_SCORED"
                   or r.get("paper_eligible") is not False
                   or r.get("live_order_authorized") is not False
                   or type(r.get("provider_receipt_count")) is not int
                   or r["provider_receipt_count"]<1
                   for r,sym in zip(rows,expected,strict=True))):
        raise ValueError("QD_NATIVE_INTAKE_SCORED_SYMBOL_ORIGIN_REFUSED")
    if catalog is not None:
        # Optional caller-supplied complete original research inventory,
        # never imply brokerage/Robinhood proof from an Alpaca roster.
        if (type(catalog) is not dict
                or catalog.get("schema")!="ATLAS_ALPACA_EQUITY_RESEARCH_INVENTORY_V1"
                or catalog.get("sha256")!=batch.get("inventory_sha256")
                or catalog.get("robinhood_brokerage_verified") is not False):
            raise ValueError("QD_NATIVE_INTAKE_RESEARCH_INVENTORY_MISMATCH")
        from scripts.observation_runtime.alpaca_equity_catalog import rotating_batch
        if rotating_batch(catalog,offset=batch.get("offset"),limit=len(expected))!=expected:
            raise ValueError("QD_NATIVE_INTAKE_RESEARCH_BATCH_MISMATCH")
    # This receipt is a score-only summary. It cannot evidence native fields,
    # even if a caller inserts optimistic ad-hoc scores/targets in a new file.
    absent=list(SOURCE_FIELDS)
    return {
        "schema":SCHEMA,
        "status":"RESEARCH_RECEIPT_VALID_NATIVE_FORWARD_INPUT_INCOMPLETE",
        "receipt_sha256":digest,
        "symbols":list(expected),
        "scored_research_count":len(rows),
        "recorded_research_lanes":[r.get("research_lane") for r in rows],
        "original_provider_evidence_in_receipt":False,
        "three_fresh_independent_valuation_estimates_verified":False,
        "missing_native_intake_fields":absent,
        "native_forward_input_complete":False,
        "native_scanner_issuer_accepted":False,
        "source_rights_accepted":False,
        "financial_clock_accepted":False,
        "paper_orders_authorized":False,
        "live_orders_authorized":False,
        "startup_authorized":False,
    }


def inspect_existing(*, root=RESEARCH, limit=8):
    if type(limit) is not int or not 1<=limit<=32:
        raise ValueError("QD_NATIVE_INTAKE_BOUNDED_RESEARCH_INVENTORY_REQUIRED")
    root=Path(root)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("QD_NATIVE_INTAKE_READONLY_RESEARCH_DIRECTORY_REQUIRED")
    found=sorted(p for p in root.iterdir() if RECEIPT.fullmatch(p.name))
    if len(found)>limit:
        raise ValueError("QD_NATIVE_INTAKE_RESEARCH_RECEIPT_COUNT_LIMIT")
    return {
        "schema":"ATLAS_QD_EXISTING_SCORED_RECEIPT_INTAKE_V1",
        "reports":[inspect_receipt(path,root=root) for path in found],
        "source_authority_verified":False,
        "native_forward_publication_created":False,
        "paper_orders_authorized":False,
    }
