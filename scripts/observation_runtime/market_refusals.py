"""Sanitized failures for inert fixture APIs; never production recovery authority."""
from __future__ import annotations

import sqlite3
from html import escape

MAX_COUNTER=2**53-1


def refusal_payload(status):
    if type(status) is not int or not 400<=status<=599:status=500
    if status==409:status=503
    reason={400:'INVALID_REQUEST',404:'UNKNOWN_RESOURCE',405:'METHOD_NOT_ALLOWED',422:'INVALID_REQUEST',
            500:'INTERNAL_ERROR',503:'DATA_UNAVAILABLE'}.get(status,'REQUEST_REFUSED')
    return {'schema':'ATLAS_MARKET_DATA_REFUSAL_V1','mode':'SYNTHETIC_REPLAY','status':'REFUSED',
            'http_status':status,'reason':reason,'rows':[],'quote_rows':[],'source_authenticated':False,
            'network_authorized':False,'startup_authorized':False,'recovery_authorized':False,'trading_authorized':False}


def install_market_refusals(app, *, html_paths,failure_observer=None):
    """Expected source failures are 503, unknown errors remain non-success 500.

    An optional trusted synchronous observer receives the original exception,
    including its cause/traceback. No raw messages/paths/inputs are logged or
    returned here. Observer completion is not durable diagnostic acknowledgement;
    a failing observer never masks the primary failure. No I/O/retries or worker
    are created. An observer must be nonblocking; no hard callback deadline is
    claimed. Default telemetry stores bounded counters, not raw exceptions.
    """
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import HTMLResponse, JSONResponse
    from starlette.exceptions import HTTPException

    if failure_observer is not None and not callable(failure_observer):
        raise ValueError('Explicit callable failure observer required')
    pages=frozenset(html_paths)
    counters={'responses':0,'observer_failures':0}
    app.state.market_failure_counts=counters

    def respond(request,error,status):
        counters['responses']=min(MAX_COUNTER,counters['responses']+1)
        if failure_observer is not None:
            try:failure_observer(error)
            except Exception:  # noqa: BLE001 -- observer failures must not mask the primary refusal
                counters['observer_failures']=min(MAX_COUNTER,counters['observer_failures']+1)
                BaseException.add_note(error,'Optional failure observer did not complete; primary failure retained.')
        body=refusal_payload(status)
        headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}
        if body['http_status']==405:headers['Allow']='GET'
        if request.url.path in pages:
            page=("<!doctype html><html lang='en'><meta charset='utf-8'><title>Atlas data unavailable</title>"
                  '<h1>Data unavailable</h1><p role="alert">No current prices or partial research are displayed. '
                  'Previously loaded data must not be treated as current.</p><p>State: '+escape(body['reason'])+
                  '</p><p>Synthetic fixture API only. No live feed, startup, recovery or trading authority.</p></html>')
            return HTMLResponse(page,status_code=body['http_status'],headers={**headers,
                'Content-Security-Policy':"default-src 'none'; frame-ancestors 'none'"})
        return JSONResponse(body,status_code=body['http_status'],headers=headers)

    async def source_failure(request,error):return respond(request,error,503)
    async def unexpected_failure(request,error):return respond(request,error,500)
    async def http_failure(request,error):return respond(request,error,error.status_code)
    async def validation_failure(request,error):return respond(request,error,422)

    for error_type in (ValueError,TypeError,KeyError,OverflowError,OSError,sqlite3.Error):
        app.add_exception_handler(error_type,source_failure)
    app.add_exception_handler(HTTPException,http_failure)
    app.add_exception_handler(RequestValidationError,validation_failure)
    # Starlette re-raises unhandled application faults after this response. The
    # server/ASGI caller retains its original error; it is never success.
    app.add_exception_handler(Exception,unexpected_failure)
