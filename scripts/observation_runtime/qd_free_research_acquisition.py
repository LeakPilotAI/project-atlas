"""Bounded genuine Alpaca/SEC acquisition; diagnostic only, never source authority.

Explicit SEC contact required. No financial writer, operational publication or
operator activation. Existing free-provider refusal reasons remain authoritative.
"""
import argparse
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))
from app.investment.alpaca_iex import Credentials
from app.investment.free_research_providers import FreeResearchBundle
from app.investment.free_research_transport import FreeResearchClient, ResearchRefused


def inspect_free_research(*, symbol, contact, credentials_path, client_factory=FreeResearchClient,
                          bundle_factory=FreeResearchBundle):
    if (type(symbol) is not str or re.fullmatch(r"[A-Z]{1,8}", symbol) is None
            or type(contact) is not str
            or re.fullmatch(r"ProjectAtlas/1\.0 [A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", contact) is None
            or contact.lower().endswith(('.invalid', '.test', '.example', '@example.com', '@example.org', '@example.net'))):
        raise ResearchRefused("QD_REAL_SYMBOL_AND_SEC_CONTACT_REQUIRED")
    credentials = Credentials.load(credentials_path)
    now = lambda: datetime.now(UTC)
    client = client_factory(cache_root=REPO / "logs" / "diagnostics" / "qd-free-research-acquisition",
                            now=now, sec_user_agent=contact, credentials=credentials,
                            max_attempts=12, seconds=60)
    if client.domain != "TLS_PUBLIC_PROVIDER":
        raise ResearchRefused("QD_REAL_PROVIDER_TRANSPORT_REQUIRED")
    data = bundle_factory(client=client, now=now).load(symbol)
    if type(data) is not dict or data.get("paper_eligible") is not False:
        raise ResearchRefused("QD_RESEARCH_NOT_DIAGNOSTIC")
    return {"schema": "ATLAS_QD_FREE_RESEARCH_ACQUISITION_V1",
            "symbol": symbol, "transport": "TLS_PUBLIC_PROVIDER",
            "provider_receipt_count": len(data["receipts"]),
            "completed_daily_bar_count": len(data["bars"]),
            "fundamental_metric_count": len(data["fundamentals"]),
            "normalization_estimates_accepted": False,
            "refusals": data["refusals"],
            "operational_source_accepted": False,
            "paper_fill_authorized": False, "live_order_authorized": False}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="MSFT")
    parser.add_argument("--sec-contact", default=os.environ.get("ATLAS_SEC_CONTACT"))
    args = parser.parse_args(argv)
    try:
        result = inspect_free_research(symbol=args.symbol, contact=args.sec_contact,
                                       credentials_path=REPO / "config/alpaca.env")
    except (ValueError, OSError, KeyError, TypeError):
        result = {"schema": "ATLAS_QD_FREE_RESEARCH_ACQUISITION_V1", "status": "REFUSED",
                  "operational_source_accepted": False, "paper_fill_authorized": False,
                  "live_order_authorized": False}
        print(json.dumps(result, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
