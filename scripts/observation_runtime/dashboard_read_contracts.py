"""Source/ASGI dashboard factory. No listener, lifespan, backend or default ports.

Keeps the original six-tab shell/URLs; safe contract panes avoid invoking the
legacy financial GET graph. No installed launcher is changed by this factory.
"""

from html import escape
from pathlib import Path

from app.services.dashboard_read_models import DashboardReadModels
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

STATIC = Path(__file__).resolve().parents[2] / "backend/app/static"
PANES = {
    "/dashboard/perps": ("perps", "Perp Day Trade"),
    "/api/investments/quality-dips/view": ("quality", "Quality Dips"),
    "/dashboard/investment": ("invest", "Investment"),
    "/dashboard/archive": ("archive", "Archive"),
    "/dashboard/command-center": ("command", "Command Center"),
    "/dashboard/prediction-paper": ("prediction", "Prediction Markets"),
}
MODEL = "/api/dashboard/read-model"
SELECTED = "/api/investments/quality-dips/selected-paper"


def build_app(*, models, port):
    if (
        type(models) is not DashboardReadModels
        or type(port) is not int
        or not 1 <= port <= 65535
    ):
        raise ValueError("EXPLICIT_DASHBOARD_READ_COMPOSITION_REQUIRED")
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    origin = f"http://127.0.0.1:{port}"
    assets = {
        "/dashboard": ((STATIC / "dashboard_hub.html").read_bytes(), "text/html"),
        "/static/atlas_ui.css": ((STATIC / "atlas_ui.css").read_bytes(), "text/css"),
        "/static/runtime_poll.js": (
            (STATIC / "runtime_poll.js").read_bytes(),
            "application/javascript",
        ),
        "/static/dashboard_read_contract.js": (
            (STATIC / "dashboard_read_contract.js").read_bytes(),
            "application/javascript",
        ),
    }

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        if (
            request.headers.getlist("host") != [origin.removeprefix("http://")]
            or request.headers.getlist("origin") not in ([], [origin])
            or request.headers.get("sec-fetch-site") == "cross-site"
            or request.method != "GET"
        ):
            response = Response(status_code=403)
        elif request.url.query and not (
            request.url.path == "/dashboard/perps" and request.url.query == "embed=1"
        ):
            response = Response(status_code=404)
        else:
            response = await call_next(request)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "Content-Security-Policy": "default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-src 'self'; frame-ancestors 'self'; base-uri 'none'; form-action 'none'",
            }
        )
        return response

    @app.get(MODEL)
    def read_model():
        try:
            return models.snapshot()
        except (ValueError, OSError, KeyError, TypeError):
            return JSONResponse(
                {
                    "schema": "ATLAS_DASHBOARD_READ_MODEL_V1",
                    "status": "UNKNOWN",
                    "startup_authorized": False,
                },
                status_code=503,
            )

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "mode": "READ_MODEL_ONLY",
            "scanner_running": False,
            "paper_trade_tracker_running": False,
            "financial_writers": False,
            "provider_connections": "UNAVAILABLE",
            "paper_startup_authorized": False,
        }

    @app.get(SELECTED)
    def selected():
        # This factory has no accepted selected-financial capability. Do not
        # mislabel a research candidate or separate account summary as one.
        return {
            "schema": "QD_SELECTED_FINANCIAL_VIEW_V1",
            "status": "UNAVAILABLE",
            "account_id": None,
            "epoch": None,
            "cash": None,
            "realized": None,
            "positions": None,
            "valuation": None,
            "report_status": "UNAVAILABLE",
            "reasons": ["NO_SELECTED_FINANCIAL_READ_CAPABILITY"],
            "startup_authorized": False,
        }

    for route, (pane, title) in PANES.items():

        def page(kind=pane, label=title):
            html = f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{escape(label)}</title><link rel="stylesheet" href="/static/atlas_ui.css"></head><body data-atlas-pane="{kind}"><main><h1>{escape(label)}</h1><p>Read-only research / simulated accounts · PAPER startup blocked</p><div id="atlas-read-model" role="status">UNAVAILABLE — waiting for verified read evidence.</div></main><script src="/static/runtime_poll.js"></script><script src="/static/dashboard_read_contract.js"></script></body></html>'
            return Response(html, media_type="text/html")

        # No query-controlled callback arguments; the closure owns pane identity.
        def bind_page(callback):
            def serve():
                return callback()

            return serve

        app.add_api_route(route, bind_page(page), methods=["GET"])
    for route, (data, mime) in assets.items():

        def bind_asset(content, media):
            def serve():
                return Response(content, media_type=media)

            return serve

        app.add_api_route(route, bind_asset(data, mime), methods=["GET"])

    @app.get("/{unavailable:path}")
    def unavailable(unavailable):
        return JSONResponse(
            {
                "status": "UNAVAILABLE",
                "reason": "NO_READ_CAPABILITY_FOR_THIS_SURFACE",
                "startup_authorized": False,
            },
            status_code=503 if unavailable.startswith("api/") else 404,
        )

    return app
