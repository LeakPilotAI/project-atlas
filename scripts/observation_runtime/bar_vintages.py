"""Explicit opt-in synthetic bar receipts; original ReplayStore is unchanged."""
from __future__ import annotations

import json
import sqlite3
from html import escape

from app.investment.offline_research import ResearchInputRefused, aware, symbol_identity

from scripts.observation_runtime.market_replay import normalize_chart
from scripts.observation_runtime.research_replay import (
    encoded,
    fingerprint,
    render_replay,
    replay_research,
)
from scripts.observation_runtime.retained_research import validate_reference
from scripts.observation_runtime.session_quality import validate_replay_observation

MAX_RECORDS=10000
MAX_RECEIPT_DECISIONS=200000
ZERO='0'*64


def _history(symbol,now,rows):
    return {'schema':'ATLAS_MARKET_REPLAY_HISTORY_V1','mode':'SYNTHETIC_REPLAY','symbol':symbol,
            'asof':aware(now).isoformat(),'network_authorized':False,'trading_enabled':False,
            'rows':rows,'more_retained_rows':False,'scope':'BOUNDED_RETAINED_BARS_NOT_FULL_SESSION'}


def _semantic(row):return {key:value for key,value in row.items() if key!='observed_at'}


def _archive(symbol,now,records):
    return {'schema':'ATLAS_BAR_RECEIPT_ARCHIVE_V1','mode':'SYNTHETIC_REPLAY','symbol':symbol,
            'asof':aware(now).isoformat(),'record_n':len(records),'records':records,
            'head':records[-1]['digest'] if records else ZERO,'network_authorized':False,
            'trading_enabled':False,'scope':'BOUNDED_RECEIPT_VINTAGES_NOT_FULL_SESSION'}


def validate_archive(archive):
    if (type(archive) is not dict or set(archive)!={'schema','mode','symbol','asof','record_n','records','head',
            'network_authorized','trading_enabled','scope'} or archive['schema']!='ATLAS_BAR_RECEIPT_ARCHIVE_V1'
            or archive['mode']!='SYNTHETIC_REPLAY' or archive['network_authorized'] is not False
            or archive['trading_enabled'] is not False or archive['scope']!='BOUNDED_RECEIPT_VINTAGES_NOT_FULL_SESSION'
            or type(archive['records']) is not list or len(archive['records'])>MAX_RECORDS
            or type(archive['record_n']) is not int or archive['record_n']!=len(archive['records'])):
        raise ResearchInputRefused('Explicit bounded denied-authority receipt archive required')
    symbol=symbol_identity(archive['symbol']);cutoff=aware(archive['asof'])
    if archive['symbol']!=symbol:raise ResearchInputRefused('Canonical receipt symbol required')
    previous=ZERO;prior=None;seen=set();assets=set()
    for index,record in enumerate(archive['records'],1):
        if (type(record) is not dict or set(record)!={'sequence','previous','row','digest'}
                or type(record['sequence']) is not int or record['sequence']!=index
                or record['previous']!=previous or record['digest']!=fingerprint({k:v for k,v in record.items() if k!='digest'})):
            raise ResearchInputRefused('Receipt chain identity/commitment mismatch')
        row=record['row'];stamp,receipt=validate_replay_observation(row,symbol=symbol,cutoff=cutoff)
        if (prior is not None and receipt<prior) or (stamp,receipt) in seen:
            raise ResearchInputRefused('Backdated or tied event receipt evidence')
        assets.add(row['asset_class'])
        if len(assets)>1:raise ResearchInputRefused('Conflicting receipt asset identity')
        seen.add((stamp,receipt));prior=receipt;previous=record['digest']
    if archive['head']!=previous:raise ResearchInputRefused('Missing committed receipt tail')
    return symbol,cutoff


def _project(archive,clock):
    selected={};visible=[];corrections=confirmations=0
    for record in archive['records']:
        row=record['row']
        if aware(row['observed_at'])>clock:break
        key=aware(row['timestamp']);old=selected.get(key)
        if old is None:selected[key]=row
        elif _semantic(old)!=_semantic(row):selected[key]=row;corrections+=1
        else:confirmations+=1
        visible.append(record)
    return {'history':_history(archive['symbol'],clock,[selected[key] for key in sorted(selected)]),
            'visible_receipt_n':len(visible),'receipt_head':visible[-1]['digest'] if visible else ZERO,
            'correction_n':corrections,'confirmation_n':confirmations}


def project_history(archive, *, now):
    _,cutoff=validate_archive(archive);clock=aware(now)
    if clock>cutoff:raise ResearchInputRefused('Decision exceeds receipt archive cutoff')
    return json.loads(encoded(_project(archive,clock)))


class BarVintageStore:
    """Caller-owned isolated SQLite only; no default path or real-store migration.

    Head and receipts commit in one transaction, detecting tail loss relative to
    that retained head. Whole-database rollback or privileged editing is outside
    this consistency contract. Caller SQLite commit is not hardware certification.
    """
    def __init__(self,connection):
        self.connection=connection
        if connection.in_transaction:raise ResearchInputRefused('Dedicated idle receipt connection required')
        with connection:
            connection.execute('CREATE TABLE IF NOT EXISTS replay_bar_receipts ('
              'symbol TEXT, sequence INTEGER, event_time TEXT, receipt_time TEXT, digest TEXT, body TEXT, '
              'PRIMARY KEY(symbol,sequence), UNIQUE(symbol,event_time,receipt_time))')
            connection.execute('CREATE TABLE IF NOT EXISTS replay_bar_receipt_heads ('
              'symbol TEXT PRIMARY KEY, sequence INTEGER, digest TEXT)')

    def _read(self,symbol):
        records=self.connection.execute('SELECT sequence,event_time,receipt_time,digest,body FROM replay_bar_receipts '
                    'WHERE symbol=? ORDER BY sequence LIMIT ?', (symbol,MAX_RECORDS+1)).fetchall()
        head=self.connection.execute('SELECT sequence,digest FROM replay_bar_receipt_heads WHERE symbol=?',(symbol,)).fetchone()
        if len(records)>MAX_RECORDS:raise ResearchInputRefused('Receipt store bound exceeded; no silent truncation')
        if head is None and records or head is not None and (not records or head!=(len(records),records[-1][3])):
            raise ResearchInputRefused('Receipt head/record count mismatch')
        decoded=[]
        for sequence,event,receipt,digest,body in records:
            value=json.loads(body)
            if (encoded(value).decode()!=body or type(value) is not dict or value.get('sequence')!=sequence
                    or value.get('digest')!=digest or not isinstance(value.get('row'),dict)
                    or value['row'].get('timestamp')!=event or value['row'].get('observed_at')!=receipt):
                raise ResearchInputRefused('Receipt stored key/body mismatch')
            decoded.append(value)
        if decoded:validate_archive(_archive(symbol,decoded[-1]['row']['observed_at'],decoded))
        return decoded

    def ingest(self,payload, *, observed_at,asset_class):
        rows=normalize_chart(payload,observed_at=observed_at,asset_class=asset_class)
        symbol=rows[0]['symbol'];db=self.connection
        if db.in_transaction:raise ResearchInputRefused('Dedicated idle receipt connection required')
        db.execute('BEGIN IMMEDIATE')
        try:
            records=self._read(symbol);initial=len(records)
            existing={(r['row']['timestamp'],r['row']['observed_at']):r for r in records}
            for row in rows:
                key=(row['timestamp'],row['observed_at']);old=existing.get(key)
                if old is not None:
                    if encoded(old['row'])!=encoded(row):raise ResearchInputRefused('Conflicting exact receipt retry')
                    continue
                if records and aware(row['observed_at'])<aware(records[-1]['row']['observed_at']):
                    raise ResearchInputRefused('New receipt cannot be backdated behind committed evidence')
                if records and row['asset_class']!=records[0]['row']['asset_class']:
                    raise ResearchInputRefused('Receipt asset identity changed')
                if len(records)>=MAX_RECORDS:raise ResearchInputRefused('Receipt store bound exceeded')
                record={'sequence':len(records)+1,'previous':records[-1]['digest'] if records else ZERO,'row':row}
                record['digest']=fingerprint(record)
                db.execute('INSERT INTO replay_bar_receipts VALUES (?,?,?,?,?,?)',
                    (symbol,record['sequence'],row['timestamp'],row['observed_at'],record['digest'],encoded(record).decode()))
                records.append(record);existing[key]=record
            if len(records)>initial:
                db.execute('INSERT INTO replay_bar_receipt_heads VALUES (?,?,?) ON CONFLICT(symbol) DO UPDATE '
                    'SET sequence=excluded.sequence,digest=excluded.digest',(symbol,len(records),records[-1]['digest']))
            db.commit()
            return len(records)-initial
        except BaseException:
            db.rollback()
            raise

    def archive(self,symbol, *, now):
        symbol=symbol_identity(symbol);clock=aware(now)
        # A read transaction binds the head and records to one SQLite snapshot.
        if self.connection.in_transaction:raise ResearchInputRefused('Dedicated idle receipt connection required')
        self.connection.execute('BEGIN')
        try:
            records=self._read(symbol)
            result=_archive(symbol,clock,[r for r in records if aware(r['row']['observed_at'])<=clock])
            validate_archive(result);self.connection.commit();return result
        except BaseException:
            self.connection.rollback()
            raise


def replay_vintages(archive,references,decisions):
    """Retain planned decisions; reuse legacy research on each known bar state."""
    archive=json.loads(encoded(archive));symbol,cutoff=validate_archive(archive)
    references=json.loads(encoded(references))
    # Reuse the existing complete reference/clock checks without selecting bars.
    plan=replay_research(_history(symbol,cutoff,[]),references,decisions)
    for reference in references:
        validate_reference(reference,symbol=symbol,cutoff=cutoff,
                           asset_class=archive['records'][0]['row']['asset_class'] if archive['records'] else None)
    clocks=[aware(row['decision_at']) for row in plan['cases']]
    work=sum(sum(aware(r['row']['observed_at'])<=clock for r in archive['records']) for clock in clocks)
    if work>MAX_RECEIPT_DECISIONS:raise ResearchInputRefused('Receipt-decision work budget exceeded')
    counts={key:0 for key in plan['status_counts']};cases=[]
    for index,clock in enumerate(clocks):
        projection=_project(archive,clock)
        known_refs=[ref for ref in references if aware(ref['available_at'])<=clock]
        result=replay_research(projection['history'],known_refs,[clock])
        case={**result['cases'][0],'index':index,**{k:v for k,v in projection.items() if k!='history'}}
        case['vintage_decision_sha256']=fingerprint({'decision_sha256':case['decision_sha256'],
                **{k:v for k,v in projection.items() if k!='history'}})
        cases.append(case);counts[case['status']]+=1
    return {'schema':'ATLAS_VINTAGE_RESEARCH_REPLAY_V1','mode':'SYNTHETIC_REPLAY','symbol':symbol,
            'archive_asof':cutoff.isoformat(),'archive_sha256':fingerprint(archive),'references_sha256':fingerprint(references),
            'planned_decision_n':len(cases),'status_counts':counts,'cases':cases,'receipt_decision_work':work,
            'bar_revision_policy':'RECEIPT_ORDERED_VALUE_CHANGES_UNCHANGED_CONFIRMATIONS_KEEP_FIRST_RECEIPT',
            'bar_revisions_supported':True,'source_authenticated':False,'monitoring_completeness_verified':False,
            'predictive_skill_established':False,'network_authorized':False,'startup_authorized':False,
            'recovery_authorized':False,'trading_authorized':False}


def render_vintages(report):
    rows=[]
    for case in report['cases']:
        rows.append('<tr>'+''.join('<td>'+escape(str(case[key]))+'</td>' for key in
          ('decision_at','visible_receipt_n','correction_n','confirmation_n','receipt_head'))+'</tr>')
    return (render_replay(report).removesuffix('</html>')+
            '<h2>Receipt-vintage evidence</h2><p>Caller-declared receipts, not authenticated arrival times. '
            'Corrections apply only after receipt; unchanged confirmations retain first value receipt. '
            'No monitoring completeness or hardware durability claim.</p><table><tr><th>Clock</th>'
            '<th>Receipts</th><th>Value corrections</th><th>Unchanged confirmations</th><th>Receipt head</th>'
            '</tr>'+''.join(rows)+'</table></html>')


def browser_vintages(report):
    text=encoded(report).decode()
    result=encoded({'schema':'ATLAS_VINTAGE_REPLAY_BROWSER_V1','report_json':text,'payload_sha256':fingerprint(report)}).decode()
    if len(result.encode())>1_000_000:raise ResearchInputRefused('Bounded vintage browser export required')
    return result


def create_vintage_app(store, *, symbols,clock,previous_closes=None,failure_observer=None):
    """In-process read-only fixture API; no server command or production mount."""
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse

    from scripts.observation_runtime.market_refusals import install_market_refusals

    if not isinstance(store,BarVintageStore) or type(symbols) not in (tuple,list) or not 1<=len(symbols)<=100:
        raise ResearchInputRefused('Explicit synthetic receipt store and bounded symbol universe required')
    allowed={symbol_identity(s) for s in symbols}
    if (previous_closes is not None and (type(previous_closes) is not dict or not set(previous_closes)<=allowed)):
        raise ResearchInputRefused('Reference vintages outside explicit universe')
    raw=encoded(previous_closes or {})
    if len(raw)>1_000_000:raise ResearchInputRefused('Reference-map byte budget exceeded')
    references=json.loads(raw)
    if any(type(rows) is not list or len(rows)>512 for rows in references.values()):
        raise ResearchInputRefused('Bounded explicit reference-vintage lists required')
    app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
    install_market_refusals(app,html_paths={'/vintage-research'},failure_observer=failure_observer)
    headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}

    def source(symbol):
        try:clean=symbol_identity(symbol)
        except ValueError as error:raise HTTPException(422,'Invalid symbol') from error
        if clean not in allowed:raise HTTPException(404,'Symbol outside explicit fixture universe')
        try:
            now=aware(clock());archive=store.archive(clean,now=now)
            return clean,now,archive
        except (ValueError,TypeError,KeyError,OverflowError,OSError,sqlite3.Error) as error:
            raise HTTPException(409,'Receipt evidence unavailable or inconsistent') from error

    def research(symbol):
        clean,now,archive=source(symbol)
        try:return replay_vintages(archive,references.get(clean,[]),[now])
        except (ValueError,TypeError,KeyError,OverflowError) as error:
            raise HTTPException(409,'Receipt research evidence refused') from error

    @app.get('/api/market-data/receipt-history')
    async def receipt_history(symbol:str):
        return JSONResponse(source(symbol)[2],headers=headers)

    @app.get('/api/market-data/vintage-research')
    async def vintage_research(symbol:str):
        return JSONResponse(research(symbol),headers=headers)

    @app.get('/vintage-research',response_class=HTMLResponse)
    async def vintage_dashboard(symbol:str):
        return HTMLResponse(render_vintages(research(symbol)),headers={**headers,
            'Content-Security-Policy':"default-src 'none'; frame-ancestors 'none'"})

    return app
