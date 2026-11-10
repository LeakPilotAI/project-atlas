"""Non-activating QD native-source/IEX quote pairing for PAPER commissioning.

This read-only boundary reuses the original QualityDipsCurrentProducer's
native source/custody readback and the authenticated IEXFeed's validated quote
cache. It does NOT create rankings, research inputs, accounts, source grants,
PAPER orders, startup/Stop authority, or a real provider connection.
A passing disposable assembly is not operational acceptance.
"""
from __future__ import annotations

from app.investment.alpaca_iex import FEED, IEXFeed
from app.services.paper_financial_replay import body, digest, strict
from app.services.quality_dips_current_producer import QualityDipsCurrentProducer

SCHEMA = "ATLAS_QD_NATIVE_IEX_READONLY_PAIRING_V1"


def _instruments(publication, now):
    if (type(publication) is not dict
            or set(publication) != {
                "schema", "source_id", "revision", "observed_at", "bundles", "monitors"
            }
            or publication["schema"] != "QD_SCANNER_PUBLICATION_V1"
            or type(publication["source_id"]) is not str
            or not publication["source_id"]
            or type(publication["revision"]) is not int
            or publication["revision"] < 1
            or type(publication["observed_at"]) is not int
            or not 0 <= now - publication["observed_at"] <= 30
            or type(publication["bundles"]) is not list
            or len(publication["bundles"]) > 16
            or type(publication["monitors"]) is not dict
            or len(publication["monitors"]) > 16):
        raise ValueError("QD_IEX_PAIRING_NATIVE_PUBLICATION_SHAPE_REQUIRED")
    instruments = {}
    for bundle in publication["bundles"]:
        if (type(bundle) is not dict or
                set(bundle) != {"board", "observation", "instrument", "quote", "publication"}):
            raise ValueError("QD_IEX_PAIRING_CURRENT_BUNDLE_REQUIRED")
        instrument, obs = bundle["instrument"], bundle["observation"]
        if (type(instrument) is not dict or type(obs) is not dict
                or obs.get("evidence_class") != "FORWARD_COLLECTION"
                or obs.get("strategy_version") != "QUALITY_DIPS_V3"
                or obs.get("execution") != "MANUAL_ONLY"
                or obs.get("symbol") != instrument.get("symbol")):
            raise ValueError("QD_IEX_PAIRING_FORWARD_OBSERVATION_REQUIRED")
        _insert(instruments, instrument)
    for ident, monitor in publication["monitors"].items():
        if (type(monitor) is not dict or type(ident) is not str
                or not ident or type(monitor.get("instrument")) is not dict
                or monitor["instrument"].get("instrument_id") != ident
                or monitor.get("symbol") != monitor["instrument"].get("symbol")
                or type(monitor.get("observed_at")) is not int
                or not 0 <= now - monitor["observed_at"] <= 30):
            raise ValueError("QD_IEX_PAIRING_MONITOR_REQUIRED")
        _insert(instruments, monitor["instrument"], allow_identical=True)
    if not instruments:
        raise ValueError("QD_IEX_PAIRING_NO_CURRENT_INSTRUMENT_SCOPE")
    if len(instruments) > 16:
        raise ValueError("QD_IEX_PAIRING_INSTRUMENT_CAPACITY")
    return instruments


def _insert(instruments, instrument, *, allow_identical=False):
    if (type(instrument) is not dict
            or type(instrument.get("symbol")) is not str
            or not instrument["symbol"]
            or type(instrument.get("instrument_id")) is not str
            or not instrument["instrument_id"]
            or instrument.get("asset_class") not in ("STOCK", "ETF")
            or instrument.get("currency") != "USD"
            or instrument.get("units") != "SHARES"):
        raise ValueError("QD_IEX_PAIRING_EXACT_STOCK_INSTRUMENT_REQUIRED")
    symbol = instrument["symbol"]
    previous = instruments.get(symbol)
    if previous is not None and (not allow_identical or previous != instrument):
        raise ValueError("QD_IEX_PAIRING_DUPLICATE_OR_CHANGED_INSTRUMENT")
    if any(name != symbol and row["instrument_id"] == instrument["instrument_id"]
           for name, row in instruments.items()):
        raise ValueError("QD_IEX_PAIRING_DUPLICATE_INSTRUMENT_IDENTITY")
    instruments[symbol] = strict(body(instrument))


def _snapshot(view, symbols, now):
    if (type(view) is not dict
            or view.get("schema") != "ATLAS_ALPACA_IEX_VIEW_V1"
            or view.get("provider") != "ALPACA"
            or view.get("feed") != "IEX"
            or view.get("feed_id") != FEED
            or view.get("size_units") != "ROUND_LOTS"
            or view.get("scope") != "SINGLE_EXCHANGE_NOT_NBBO"
            or view.get("error") is not None
            or view.get("connection") != "CONNECTED"
            or view.get("authenticated") is not True
            or view.get("subscribed") is not True
            or view.get("paper_startup_authorized") is not False
            or type(view.get("observed_at")) not in (int, float)
            or not 0 <= view["observed_at"] - now <= 1
            or type(view.get("quotes")) is not list):
        raise ValueError("QD_IEX_PAIRING_CONNECTED_AUTHENTICATED_FEED_REQUIRED")
    quotes = {}
    for q in view["quotes"]:
        if (type(q) is not dict or type(q.get("symbol")) is not str
                or q["symbol"] in quotes):
            raise ValueError("QD_IEX_PAIRING_QUOTE_ROSTER_INVALID")
        quotes[q["symbol"]] = q
    if not set(symbols) <= set(quotes):
        raise ValueError("QD_IEX_PAIRING_ALL_REQUIRED_SYMBOLS_MUST_BE_SUBSCRIBED")
    result = {}
    for symbol in symbols:
        q = quotes[symbol]
        if q.get("state") != "FRESH":
            result[symbol] = None
            continue
        if (type(q.get("source_ns")) is not int or q["source_ns"] <= 0
                or type(q.get("sequence")) is not int or q["sequence"] <= 0
                # Direct offline feed.receive() fixtures use generation zero;
                # a real feed.run() increments it. Neither grants PAPER authority.
                or type(q.get("generation")) is not int or q["generation"] < 0
                or not 0 <= view["observed_at"] - q["source_ns"] / 1_000_000_000 <= 5):
            raise ValueError("QD_IEX_PAIRING_FRESH_QUOTE_IDENTITY_INVALID")
        result[symbol] = (q["generation"], q["sequence"], q["source_ns"])
    return result


def inspect(*, source, feed):
    """Read paired source ports; never infer operational or financial acceptance."""
    if (type(source) is not QualityDipsCurrentProducer
            or type(feed) is not IEXFeed
            or feed.clock is not source.clock
            or source.execution_domain not in ("OPERATIONAL", "DISPOSABLE")):
        raise ValueError("QD_IEX_PAIRING_EXPLICIT_SOURCE_AND_CLOCK_REQUIRED")
    start = source.clock()
    if type(start) is not int or start < 0:
        raise ValueError("QD_IEX_PAIRING_SOURCE_CLOCK_REQUIRED")
    # Underlying reader rechecks original input acceptance, native archive
    # replay, publication custody, revision and provenance on every call.
    publication = strict(body(source.read_publication(0.2)))
    instruments = _instruments(publication, start)
    symbols = sorted(instruments)
    before = feed.snapshot()
    first = _snapshot(before, symbols, start)
    after = strict(body(source.read_publication(0.2)))
    second = _snapshot(feed.snapshot(), symbols, start)
    end = source.clock()
    if (type(end) is not int or not 0 <= end - start <= 1
            or publication != after
            or first != second):
        raise ValueError("QD_IEX_PAIRING_NATIVE_OR_QUOTE_CUT_CHANGED")
    missing = [symbol for symbol in symbols if first[symbol] is None]
    paired = not missing
    return {
        "schema": SCHEMA,
        "status": ("DATA_ONLY_CURRENT_PAIRING_NOT_FINANCIAL_AUTHORITY"
                   if paired else "DATA_ONLY_REQUIRED_QUOTE_MISSING_NO_FINANCIAL_AUTHORITY"),
        "source_execution_domain": source.execution_domain,
        "source_id_digest": digest(publication["source_id"]),
        "native_publication_revision": publication["revision"],
        "native_publication_digest": digest(publication),
        "required_symbols": symbols,
        "fresh_quote_symbols": [symbol for symbol in symbols if symbol not in missing],
        "missing_or_stale_quote_symbols": missing,
        "complete_data_only_pairing": paired,
        "source_readback_invoked": True,
        "source_issuer_independently_accepted": False,
        "entitlements_independently_accepted": False,
        "financial_clock_independently_qualified": False,
        "continuous_quote_delivery_proven": False,
        "native_financial_issuer_published": False,
        "financial_paper_accounts_created": False,
        "paper_orders_authorized": False,
        "live_orders_authorized": False,
        "startup_authorized": False,
    }
