"""Offline chart-fixture ingestion and a read-only ASGI dashboard, never production startup.

Caller owns the SQLite connection and supplies the clock. No transport, credentials,
default storage path, scheduler, trading imports or entitlement inference exists here.
"""
from __future__ import annotations

import hashlib
import html
import json
from builtins import BaseExceptionGroup
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from math import isfinite
from urllib.parse import quote

from app.investment.offline_research import (
    ET,
    ResearchInputRefused,
    aware,
    equity_session,
    number,
    symbol_identity,
    validated_candles,
)


def _validate_optional_market_identity(metadata,asset_class):
    """Missing fixture metadata is not proof; explicit contradictions refuse.

    No timezone offset is inferred from a fixed gmtoffset (which may reflect a
    different DST date). No listing, licensing or adjustment guarantee follows.
    """
    if 'exchangeTimezoneName' in metadata and metadata['exchangeTimezoneName']!='America/New_York':
        raise ValueError('Unsupported or contradictory exchange timezone')
    expected={'US_EQUITY':'EQUITY','US_ETF':'ETF'}[asset_class]
    for field in ('instrumentType','quoteType'):
        if field in metadata and metadata[field]!=expected:
            raise ValueError('Contradictory instrument identity')


def normalize_chart(payload, *, observed_at, asset_class,diagnostic_only=False):
    """Validate the documented fixture subset of Yahoo chart-shaped minute bars.

    Timestamp is bar START; only completed bars are accepted. A bar close is never
    represented as a trade/quote, consolidated feed or proof of provider permission.
    Nonzero unknown-unit provider delay refuses ordinary ingestion. The explicit
    diagnostic-only path retains values without admitting them to either store;
    absent/zero metadata still does not establish live-feed status or entitlements.
    """
    now = aware(observed_at)
    if type(diagnostic_only) is not bool:
        raise ResearchInputRefused('Explicit diagnostic-only boolean required')
    if asset_class not in {"US_EQUITY", "US_ETF"}:
        raise ResearchInputRefused("Explicit equity/ETF asset class required")
    try:
        chart = payload["chart"]
        results = chart["result"]
        if chart.get("error") is not None or len(results) != 1:
            raise ValueError("One successful chart result required")
        result = results[0]
        meta = result["meta"]
        _validate_optional_market_identity(meta,asset_class)
        if 'exchangeDataDelayedBy' in meta:
            delay=meta['exchangeDataDelayedBy']
            if type(delay) is not int or not 0<=delay<=86400:
                raise ValueError('Malformed chart delay metadata')
            if delay and not diagnostic_only:
                raise ValueError('Unknown-unit delayed chart is diagnostic evidence only')
        symbol = symbol_identity(meta["symbol"])
        if meta["currency"] != "USD" or meta["dataGranularity"] != "1m":
            raise ValueError("Only explicit USD minute bars supported")
        timestamps = result["timestamp"]
        quotes = result["indicators"]["quote"]
        if len(quotes) != 1 or not isinstance(timestamps, list) or not 1 <= len(timestamps) <= 10000:
            raise ValueError("Bounded single chart series required")
        quote = quotes[0]
        keys = ("open", "high", "low", "close", "volume")
        if any(not isinstance(quote[k], list) or len(quote[k]) != len(timestamps) for k in keys):
            raise ValueError("Aligned OHLCV arrays required")
        raw = []
        for i, ts in enumerate(timestamps):
            if type(ts) is not int:
                raise ValueError("Integer event seconds required")
            start = datetime.fromtimestamp(ts, UTC)
            if start + timedelta(minutes=1) > now:
                raise ValueError("Incomplete or future bar")
            raw.append({"timestamp": start, **{k.title(): quote[k][i] for k in keys}})
        rows = validated_candles(symbol, raw, now=now)
    except (KeyError, TypeError, ValueError, OverflowError, OSError) as exc:
        raise ResearchInputRefused("Invalid chart fixture") from exc
    return [{"symbol": symbol, "asset_class": asset_class, "currency": "USD",
             "source": "YAHOO_CHART_SHAPED_FIXTURE", "data_mode": "SYNTHETIC_REPLAY",
             "price_kind": "COMPLETED_MINUTE_BAR_CLOSE", "interval_seconds": 60,
             "timestamp": row["timestamp"].isoformat(),
             "bar_end": (row["timestamp"] + timedelta(minutes=1)).isoformat(),
             "observed_at": now.isoformat(), "session": equity_session(row["timestamp"]),
             "open": row["Open"], "high": row["High"], "low": row["Low"],
             "close": row["Close"], "volume": row["Volume"]} for row in rows]


def normalize_quote(payload, *, observed_at, asset_class):
    """Explicit quoteResponse fixture subset; provider delay never means live.

    Select the current session's timestamped field only. A previous regular close
    cannot substitute for missing pre/post-market evidence. This is a reference
    price, not bid/ask depth, order eligibility or an executable quote.
    """
    now = aware(observed_at)
    if asset_class not in {"US_EQUITY", "US_ETF"}:
        raise ResearchInputRefused("Explicit equity/ETF asset class required")
    session = equity_session(now)
    prefix = {"PRE_MARKET": "preMarket", "REGULAR": "regularMarket",
              "AFTER_HOURS": "postMarket"}.get(session)
    if prefix is None:
        raise ResearchInputRefused("No supported current quote session")
    try:
        response = payload["quoteResponse"]
        if response.get("error") is not None or len(response["result"]) != 1:
            raise ValueError("One successful quote required")
        quote = response["result"][0]
        _validate_optional_market_identity(quote,asset_class)
        symbol = symbol_identity(quote["symbol"])
        if quote["currency"] != "USD":
            raise ValueError("Explicit USD quote required")
        ts = quote[prefix + "Time"]
        if type(ts) is not int:
            raise ValueError("Integer quote event seconds required")
        stamp = datetime.fromtimestamp(ts, UTC)
        price = number(quote[prefix + "Price"], "quote price")
        delay = quote["exchangeDataDelayedBy"]
        if type(delay) is not int or not 0 <= delay <= 86400:
            raise ValueError("Explicit bounded provider delay required")
        if stamp > now or equity_session(stamp) != session or stamp.astimezone(ET).date() != now.astimezone(ET).date():
            raise ValueError("Quote event session/time mismatch")
    except (KeyError, TypeError, ValueError, OverflowError, OSError) as exc:
        raise ResearchInputRefused("Invalid quote fixture") from exc
    return {"symbol": symbol, "asset_class": asset_class, "currency": "USD",
            "timestamp": stamp.isoformat(), "observed_at": now.isoformat(),
            "price": price, "session": session, "provider_reported_delay": delay,
            "provider_delay_unit": "UNVERIFIED_FIXTURE_METADATA",
            "source": "YAHOO_QUOTE_RESPONSE_SHAPED_FIXTURE", "data_mode": "SYNTHETIC_REPLAY",
            "price_kind": "REFERENCE_QUOTE_NOT_EXECUTABLE"}


class ReplayStore:
    """Explicit isolated SQLite repository; no migration of any Atlas store.

    Commit acknowledges SQLite's configured transaction boundary, not hardware
    power-loss safety or a backup. Provider corrections require a separate contract.
    Conflicting repeat bars are refused instead of silently replaced.
    """

    def __init__(self, connection):
        self.connection = connection
        self._read_view_fault = None
        if connection.in_transaction:
            raise ResearchInputRefused('Dedicated idle replay connection required')
        connection.execute("CREATE TABLE IF NOT EXISTS replay_bars ("
                           "symbol TEXT, event_time TEXT, digest TEXT, body TEXT, "
                           "PRIMARY KEY(symbol,event_time))")
        connection.execute("CREATE TABLE IF NOT EXISTS replay_quotes ("
                           "symbol TEXT, event_time TEXT, digest TEXT, body TEXT, "
                           "PRIMARY KEY(symbol,event_time))")
        connection.commit()

    def _available(self):
        if self._read_view_fault is not None:
            raise ResearchInputRefused('Unconfirmed read-view cleanup; store instance refuses further operations') from self._read_view_fault

    def _close_read_view(self):
        if not self.connection.in_transaction:
            raise ResearchInputRefused('Read view ended before owned cleanup')
        if getattr(self.connection, 'autocommit', None) is True:
            self.connection.execute('ROLLBACK')
        else:
            self.connection.rollback()
        if self.connection.in_transaction:
            raise ResearchInputRefused('Read view remains active after cleanup')

    @contextmanager
    def read_view(self):
        """One caller-serialized SQLite snapshot; no commit or writer exclusion.

        Raw same-connection SQL is outside this cooperative contract. No durable
        recovery fence or protection against external/privileged actors is added.
        """
        self._available()
        if self.connection.in_transaction:
            raise ResearchInputRefused('Unrelated or nested caller transaction cannot be adopted')
        try:
            self.connection.execute('BEGIN')
            if not self.connection.in_transaction:
                raise ResearchInputRefused('Read view did not begin')
        except BaseException as error:
            # BEGIN ownership is unconfirmed: never roll back a transaction that
            # could belong to another caller. Retain refusal on this instance.
            self._read_view_fault=error
            raise
        try:
            yield
        except BaseException as operation_error:
            try:self._close_read_view()
            except BaseException as cleanup_error:
                combined=BaseExceptionGroup('Read operation and cleanup failed',[operation_error,cleanup_error])
                self._read_view_fault=combined
                raise combined from cleanup_error
            raise
        else:
            try:self._close_read_view()
            except BaseException as cleanup_error:
                self._read_view_fault=cleanup_error
                raise

    def ingest(self, payload, *, observed_at, asset_class):
        rows = normalize_chart(payload, observed_at=observed_at, asset_class=asset_class)
        return self._insert(rows, "replay_bars")

    def ingest_quote(self, payload, *, observed_at, asset_class):
        row = normalize_quote(payload, observed_at=observed_at, asset_class=asset_class)
        return self._insert([row], "replay_quotes")

    @contextmanager
    def _write_batch(self):
        """Own one explicit transaction even when implicit DML transactions are off."""
        native_autocommit = getattr(self.connection, 'autocommit', None) is True
        with self.connection:
            self.connection.execute('BEGIN')
            try:
                yield
                if native_autocommit:
                    self.connection.execute('COMMIT')
            except BaseException as operation_error:
                if native_autocommit:
                    try:
                        if self.connection.in_transaction:
                            self.connection.execute('ROLLBACK')
                    except BaseException as cleanup_error:
                        combined = BaseExceptionGroup('Replay write and rollback failed', [operation_error, cleanup_error])
                        self._read_view_fault = combined
                        raise combined from cleanup_error
                raise
        if self.connection.in_transaction:
            error = ResearchInputRefused('Replay write transaction remains active after cleanup')
            self._read_view_fault = error
            raise error

    def _insert(self, rows, table):
        self._available()
        if self.connection.in_transaction:
            raise ResearchInputRefused('Replay writes require an idle connection; caller writes are never committed implicitly')
        if table not in {"replay_bars", "replay_quotes"}:
            raise ResearchInputRefused("Unknown replay store")
        inserted = 0
        with self._write_batch():
            for row in rows:
                # Retrieval latency is provenance, not a new market event identity.
                identity = {k: v for k, v in row.items() if k != "observed_at"}
                body = json.dumps(row, sort_keys=True)
                digest = hashlib.sha256(body.encode()).hexdigest()
                prior = self.connection.execute(
                    f"SELECT digest,body FROM {table} WHERE symbol=? AND event_time=?",
                    (row["symbol"], row["timestamp"])).fetchone()
                if prior:
                    if (type(prior[1]) is not str or type(prior[0]) is not str
                            or hashlib.sha256(prior[1].encode()).hexdigest() != prior[0]):
                        raise ResearchInputRefused("Retained bar integrity mismatch")
                    try:
                        prior_row = json.loads(prior[1])
                        if type(prior_row) is not dict:
                            raise ValueError("Retained duplicate must be an object")
                    except (TypeError, ValueError) as exc:
                        raise ResearchInputRefused("Retained duplicate JSON mismatch") from exc
                    if {k: v for k, v in prior_row.items() if k != "observed_at"} != identity:
                        raise ResearchInputRefused("Conflicting retained bar")
                    # Equality alone admits bool/int aliases and collapsed duplicate
                    # JSON keys. A duplicate ack requires the retained read contract.
                    self._decode((prior[1], prior[0], row["timestamp"]), row["symbol"], table=table)
                    continue
                self.connection.execute(f"INSERT INTO {table} VALUES (?,?,?,?)",
                                        (row["symbol"], row["timestamp"], digest, body))
                inserted += 1
        return inserted

    def quote_snapshot(self, symbols, *, now, max_age_seconds=30):
        self._available()
        current = aware(now)
        if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 120:
            raise ResearchInputRefused("Bounded quote freshness threshold required")
        if not isinstance(symbols, (list, tuple)) or not 1 <= len(symbols) <= 100:
            raise ResearchInputRefused("Explicit bounded symbols required")
        rows = []
        for symbol in sorted({symbol_identity(s) for s in symbols}):
            row,retained = self._latest_observed(symbol,current,'replay_quotes')
            if row is None:
                rows.append({"symbol": symbol, "status": "NOT_YET_OBSERVED" if retained else "UNAVAILABLE", "price": None})
                continue
            age = (current - aware(row["timestamp"])).total_seconds()
            status = "FRESH" if (0 <= age <= max_age_seconds
                                  and equity_session(current) == row["session"]
                                  and current.astimezone(ET).date() == aware(row["timestamp"]).astimezone(ET).date()) else "STALE"
            if row["provider_reported_delay"]:
                status = "DELAYED"
            rows.append({**row, "status": status, "age_seconds": age,
                         "reference_price": row["price"],
                         "price": row["price"] if status == "FRESH" else None})
        return rows

    def history(self, symbol, *, now, limit=100):
        """Bounded retained completed bars, without a current-price/coverage claim."""
        self._available()
        symbol = symbol_identity(symbol)
        current = aware(now)
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ResearchInputRefused("Bounded historical row limit required")
        records = self.connection.execute(
            "SELECT body,digest,event_time FROM replay_bars WHERE symbol=? AND event_time<=? "
            "ORDER BY event_time DESC LIMIT 10001", (symbol, current.isoformat())).fetchall()
        window_limited = len(records) > 10000
        eligible = []
        for record in records[:10000]:
            row = self._decode(record, symbol)
            if aware(row["observed_at"]) <= current and aware(row["bar_end"]) <= current:
                eligible.append(row)
        return {"schema": "ATLAS_MARKET_REPLAY_HISTORY_V1", "mode": "SYNTHETIC_REPLAY",
                "symbol": symbol, "asof": current.isoformat(), "network_authorized": False,
                "trading_enabled": False, "rows": list(reversed(eligible[:limit])),
                "more_retained_rows": len(eligible) > limit or window_limited,
                "scope": "BOUNDED_RETAINED_BARS_NOT_FULL_SESSION"}

    def snapshot(self, symbols, *, now, max_age_seconds=180):
        self._available()
        current = aware(now)
        if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 900:
            raise ResearchInputRefused("Bounded freshness threshold required")
        if not isinstance(symbols, (list, tuple)) or not 1 <= len(symbols) <= 100:
            raise ResearchInputRefused("Explicit bounded symbols required")
        output = []
        for symbol in sorted({symbol_identity(s) for s in symbols}):
            row,retained = self._latest_observed(symbol,current,'replay_bars')
            if row is None:
                output.append({"symbol": symbol, "status": "NOT_YET_OBSERVED", "price": None, "reference_close": None}
                              if retained else {"symbol": symbol, "status": "UNAVAILABLE", "price": None})
                continue
            age = (current - aware(row["bar_end"])).total_seconds()
            same_session = equity_session(current) == row["session"] and (
                current.astimezone(ET).date() == aware(row["timestamp"]).astimezone(ET).date())
            status = "FRESH" if 0 <= age <= max_age_seconds and same_session else "STALE"
            coverage = self._coverage(symbol, row, current)
            output.append({**row, "status": status, "age_seconds": age,
                           "price": row["close"] if status == "FRESH" else None,
                           "reference_close": row["close"],
                           "coverage": coverage})
        return {"schema": "ATLAS_MARKET_REPLAY_V1", "mode": "SYNTHETIC_REPLAY",
                "asof": current.isoformat(), "network_authorized": False,
                "trading_enabled": False, "coverage": "OBSERVED_BARS_ONLY_NO_GAP_IMPUTATION",
                "rows": output}

    def _latest_observed(self,symbol,current,table):
        """Newest eligible event, never newest retrieval; bounded lazy scan.

        Future receipts cannot obscure earlier known data. A search exhausting
        its bound refuses rather than claiming absence or current freshness.
        """
        if table not in {'replay_bars','replay_quotes'}:
            raise ResearchInputRefused('Unknown replay store')
        cursor=self.connection.execute(f'SELECT body,digest,event_time FROM {table} WHERE symbol=? '
                    'ORDER BY event_time DESC LIMIT 10001',(symbol,))
        retained=False
        try:
            for index,found in enumerate(cursor):
                retained=True
                if index>=10000:raise ResearchInputRefused('As-of selection search bound exceeded')
                row=self._decode(found,symbol,table=table)
                event=aware(row['timestamp']);receipt=aware(row['observed_at'])
                end=aware(row['bar_end']) if table=='replay_bars' else event
                if not event<=end<=receipt:
                    raise ResearchInputRefused('Retained event/receipt chronology mismatch')
                if receipt<=current:return row,True
            return None,retained
        finally:
            cursor.close()

    @staticmethod
    def _decode(found, symbol, *, table="replay_bars"):
        if (type(found[0]) is not str or type(found[1]) is not str
                or hashlib.sha256(found[0].encode()).hexdigest() != found[1]):
            raise ResearchInputRefused("Retained bar integrity mismatch")
        def unique_object(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError("Duplicate retained JSON field")
                value[key] = item
            return value
        try:
            row = json.loads(found[0], object_pairs_hook=unique_object)
            if type(row) is not dict or row.get("symbol") != symbol or row.get("timestamp") != found[2]:
                raise ResearchInputRefused("Retained row/query identity mismatch")
            common = {"symbol", "asset_class", "currency", "source", "data_mode", "price_kind",
                      "timestamp", "observed_at", "session"}
            bar_fields = {"interval_seconds", "bar_end", "open", "high", "low", "close", "volume"}
            quote_fields = {"price", "provider_reported_delay", "provider_delay_unit"}
            if table not in {"replay_bars", "replay_quotes"}:
                raise ValueError("Unknown retained source")
            bar = table == "replay_bars"
            if (set(row) != common | (bar_fields if bar else quote_fields)
                    or row["asset_class"] not in {"US_EQUITY", "US_ETF"} or row["currency"] != "USD"
                    or row["data_mode"] != "SYNTHETIC_REPLAY"
                    or row["source"] != ("YAHOO_CHART_SHAPED_FIXTURE" if bar else "YAHOO_QUOTE_RESPONSE_SHAPED_FIXTURE")
                    or row["price_kind"] != ("COMPLETED_MINUTE_BAR_CLOSE" if bar else "REFERENCE_QUOTE_NOT_EXECUTABLE")):
                raise ValueError("Retained source schema mismatch")
            stamp = aware(row["timestamp"])
            receipt = aware(row["observed_at"])
            if stamp > receipt:
                raise ResearchInputRefused("Retained event/receipt chronology mismatch")
            if (stamp.isoformat() != row["timestamp"] or receipt.isoformat() != row["observed_at"]
                    or stamp.microsecond or equity_session(stamp) != row["session"]
                    or row["session"] == "CLOSED"):
                raise ValueError("Retained observation timing mismatch")
            prices = ("open", "high", "low", "close") if bar else ("price",)
            if any(type(row[field]) not in (int, float) or not isfinite(row[field]) or row[field] <= 0 for field in prices):
                raise ValueError("Retained price must be a finite normalized number")
            if bar:
                if (type(row["interval_seconds"]) is not int or row["interval_seconds"] != 60
                        or type(row["volume"]) is not int or not 0 <= row["volume"] <= 2**53 - 1
                        or row["bar_end"] != (stamp + timedelta(minutes=1)).isoformat()
                        or aware(row["bar_end"]) > receipt):
                    raise ValueError("Retained minute/volume mismatch")
                validated_candles(symbol, [{"timestamp": stamp, **{k.title(): row[k] for k in
                    ("open", "high", "low", "close", "volume")}}], now=receipt)
            elif (type(row["provider_reported_delay"]) is not int or not 0 <= row["provider_reported_delay"] <= 86400
                    or row["provider_delay_unit"] != "UNVERIFIED_FIXTURE_METADATA"):
                raise ValueError("Retained quote delay mismatch")
        except ResearchInputRefused:
            raise
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ResearchInputRefused("Retained observation schema mismatch") from exc
        return row

    def _coverage(self, symbol, latest, current):
        # Bounded read, explicitly limited to the observed interval of the latest
        # session/date. No claim of complete history since exchange/session open.
        day = aware(latest["timestamp"]).astimezone(ET).date()
        start = datetime.combine(day, datetime.min.time(), ET).astimezone(UTC).isoformat()
        records = self.connection.execute(
            "SELECT body,digest,event_time FROM replay_bars WHERE symbol=? AND event_time>=? AND event_time<=? "
            "ORDER BY event_time DESC LIMIT 10001", (symbol, start, latest["timestamp"])).fetchall()
        if len(records) > 10000:
            return {"status": "WINDOW_LIMIT", "missing_minutes": None}
        rows = [self._decode(record, symbol) for record in records]
        times = [aware(r["timestamp"]) for r in rows if r["session"] == latest["session"]
                 and aware(r["timestamp"]).astimezone(ET).date() == day
                 and aware(r["observed_at"]) <= current]
        expected = int((max(times) - min(times)).total_seconds() / 60) + 1
        return {"status": "GAPS" if expected > len(times) else "OBSERVED_WINDOW_CONTIGUOUS",
                "observed_bars": len(times), "missing_minutes": expected - len(times),
                "window_start": min(times).isoformat(), "window_end": max(times).isoformat(),
                "scope": "FIRST_TO_LAST_OBSERVED_BAR_NOT_FULL_SESSION"}


def render_dashboard(snapshot):
    """Server-rendered offline UI: missing/stale values never masquerade as live."""
    cells = []
    for row in snapshot["rows"]:
        values = (row["symbol"], row["status"], row.get("session", "UNKNOWN"),
                  row.get("price") if row.get("price") is not None else "Unavailable",
                  row.get("timestamp", "Missing"), row.get("source", "Missing"),
                  row.get("coverage", {}).get("status", "UNKNOWN"))
        link=("<td><a href='/quality?symbol="+quote(row['symbol'],safe='')+"'>Quality windows</a> | "
              "<a href='/research?symbol="+quote(row['symbol'],safe='')+"'>Descriptive research</a></td>")
        cells.append("<tr>" + "".join(f"<td>{html.escape(str(v))}</td>" for v in values) + link + "</tr>")
    return ("<!doctype html><html lang='en'><meta charset='utf-8'><title>Atlas replay</title>"
            "<h1>Atlas market-data replay</h1><p>Synthetic fixtures only. No live feed or trading authority.</p>"
            "<p><a href='/quote-quality'>Quote-reference quality</a></p>"
            "<table><caption>Completed minute-bar closes, not executable quotes</caption>"
            "<thead><tr><th>Symbol</th><th>Freshness</th><th>Session</th><th>Bar close</th>"
            "<th>Event time</th><th>Source</th><th>Observed-window coverage</th><th>Timeline</th></tr></thead><tbody>"
            + "".join(cells) + "</tbody></table></html>")


def create_replay_app(store, *, symbols, clock, previous_closes=None,failure_observer=None):
    """Factory only; not mounted by Atlas and has no network/server launch command."""
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.responses import HTMLResponse, JSONResponse

    from scripts.observation_runtime.market_refusals import install_market_refusals

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    install_market_refusals(app,html_paths={'/','/quality','/quote-quality','/research'},failure_observer=failure_observer)
    if type(symbols) not in (list,tuple) or not 1<=len(symbols)<=100:
        raise ResearchInputRefused('Explicit bounded fixture symbol universe required')
    symbols=tuple(sorted({symbol_identity(s) for s in symbols}))
    allowed_symbols = {symbol_identity(s) for s in symbols}
    if previous_closes is not None and (type(previous_closes) is not dict or not set(previous_closes)<=allowed_symbols):
        raise ResearchInputRefused('Reference map outside explicit replay universe')
    references=json.loads(json.dumps(previous_closes or {},allow_nan=False))

    def research_report(symbol,limit):
        from scripts.observation_runtime.retained_research import (
            retained_research,
            unavailable_research,
        )

        try:
            clean=symbol_identity(symbol)
        except ResearchInputRefused as error:
            raise HTTPException(422,'Invalid symbol') from error
        if clean not in allowed_symbols:
            raise HTTPException(404,'Symbol outside explicit replay universe')
        now=clock()
        if clean not in references:
            return unavailable_research(clean,now=now,status='INSUFFICIENT_REFERENCE')
        history=store.history(clean,now=now,limit=limit)
        # Calculation failures use the shared sanitized non-success handler,
        # preserving original observer evidence after the owned read view closes.
        return retained_research(history,references[clean],now=now)

    @app.get('/api/market-data/research')
    async def research(symbol: str, limit: int = Query(1000,ge=1,le=1000)):
        with store.read_view():
            return JSONResponse(research_report(symbol,limit),headers={'Cache-Control':'no-store'})

    @app.get('/research',response_class=HTMLResponse)
    async def research_dashboard(symbol: str, limit: int = Query(1000,ge=1,le=1000)):
        from scripts.observation_runtime.retained_research import (
            render_retained_research,
        )

        with store.read_view():
            return HTMLResponse(render_retained_research(research_report(symbol,limit)),headers={
                'Cache-Control':'no-store','Content-Security-Policy':"default-src 'none'; frame-ancestors 'none'",
                'X-Content-Type-Options':'nosniff'})

    def quote_quality_report():
        from scripts.observation_runtime.quote_quality import quote_quality

        now=clock()
        return quote_quality(store.quote_snapshot(symbols,now=now),now=now)

    @app.get('/api/market-data/quote-quality')
    async def quote_quality_data():
        with store.read_view():
            return JSONResponse(quote_quality_report(),headers={'Cache-Control':'no-store'})

    @app.get('/quote-quality',response_class=HTMLResponse)
    async def quote_quality_dashboard():
        from scripts.observation_runtime.quote_quality import render_quote_quality

        with store.read_view():
            return HTMLResponse(render_quote_quality(quote_quality_report()),headers={
                'Cache-Control':'no-store','Content-Security-Policy':"default-src 'none'; frame-ancestors 'none'",
                'X-Content-Type-Options':'nosniff'})

    def quality_report(symbol, limit):
        from scripts.observation_runtime.session_quality import session_quality

        try:
            clean = symbol_identity(symbol)
        except ResearchInputRefused as error:
            raise HTTPException(422, "Invalid symbol") from error
        if clean not in allowed_symbols:
            raise HTTPException(404, "Symbol outside explicit replay universe")
        now = clock()
        return session_quality(store.history(clean, now=now, limit=limit), now=now)

    @app.get("/api/market-data/quality")
    async def quality(symbol: str, limit: int = Query(1000, ge=1, le=1000)):
        with store.read_view():
            return JSONResponse(quality_report(symbol,limit), headers={"Cache-Control": "no-store"})

    @app.get("/quality", response_class=HTMLResponse)
    async def quality_dashboard(symbol: str, limit: int = Query(1000, ge=1, le=1000)):
        from scripts.observation_runtime.session_quality import render_session_quality

        with store.read_view():
            return HTMLResponse(render_session_quality(quality_report(symbol,limit)),headers={
                "Cache-Control":"no-store","Content-Security-Policy":"default-src 'none'; frame-ancestors 'none'",
                "X-Content-Type-Options":"nosniff"})

    @app.get("/api/market-data/history")
    async def historical_bars(symbol: str, limit: int = Query(100, ge=1, le=1000)):
        try:
            clean = symbol_identity(symbol)
        except ResearchInputRefused as error:
            raise HTTPException(422, "Invalid symbol") from error
        if clean not in allowed_symbols:
            raise HTTPException(404, "Symbol outside explicit replay universe")
        with store.read_view():
            return JSONResponse(store.history(clean, now=clock(), limit=limit), headers={"Cache-Control": "no-store"})

    @app.get("/api/market-data")
    async def market_data():
        with store.read_view():
            now = clock()
            return JSONResponse({**store.snapshot(symbols, now=now), "quote_rows": store.quote_snapshot(symbols, now=now)},
                                headers={"Cache-Control": "no-store"})

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        with store.read_view():
            now = clock()
            bars = render_dashboard(store.snapshot(symbols, now=now))
            quote_rows = store.quote_snapshot(symbols, now=now)
            quote_table = "<h2>Timestamped quote references</h2><p>Separate from bar closes; no execution authority.</p>"
            quote_table += ("<table><tr><th>Symbol</th><th>Status</th><th>Reference quote</th>"
                            "<th>Event time</th><th>Source</th><th>Reported delay (unit unverified)</th></tr>")
            for row in quote_rows:
                quote_table += "<tr>" + "".join("<td>" + html.escape(str(v)) + "</td>" for v in
                    (row["symbol"], row["status"], row["price"] if row["price"] is not None else "Unavailable",
                     row.get("timestamp", "Missing"), row.get("source", "Missing"),
                     row.get("provider_reported_delay", "Unknown"))) + "</tr>"
            return HTMLResponse(bars.replace("</html>", quote_table + "</table></html>"), headers={
                "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
                "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})

    return app
