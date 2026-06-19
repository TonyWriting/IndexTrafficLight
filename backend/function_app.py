"""Azure Functions entry point for QDII ETF premium APIs."""

import json
import logging
from datetime import date, timedelta

import azure.functions as func

from shared.config import TRACKED_ETFS, EtfConfig
from shared.dashboard import build_dashboard_snapshot
from shared.pipeline import refresh_etf_premium
from shared.storage import (
    get_dashboard_snapshot,
    get_latest_premium,
    get_premium_history,
    upsert_dashboard_snapshot,
)

app = func.FunctionApp()
logger = logging.getLogger(__name__)


def _json_response(body: object, status_code: int = 200) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(body, ensure_ascii=False, separators=(",", ":")),
        status_code=status_code,
        mimetype="application/json",
    )


def _invalid_code_response(code: str) -> func.HttpResponse:
    return _json_response(
        {
            "error": f"Invalid fund code: {code}",
            "valid": list(TRACKED_ETFS.keys()),
        },
        status_code=400,
    )


def _date_param(req: func.HttpRequest, name: str) -> str:
    value = req.params.get(name, "")
    if not value:
        return ""
    date.fromisoformat(value)
    return value


def _etf_summary(config: EtfConfig) -> dict:
    return {
        "code": config.code,
        "name": config.name,
        "short_name": config.short_name,
        "tracking_index": config.tracking_index,
        "tracking_index_name": config.tracking_index_name,
        "latest": get_latest_premium(config.code),
    }


def _refresh_recent_and_update_dashboard() -> None:
    """Refresh recent ETF premium data after China market close."""
    end = date.today()
    start = end - timedelta(days=7)

    for config in TRACKED_ETFS.values():
        try:
            result = refresh_etf_premium(
                config,
                start_date=start.isoformat(),
                end_date=end.isoformat(),
            )
            logger.info(
                "Updated %s: price=%d nav=%d premium=%d",
                config.name,
                result.price_written,
                result.nav_written,
                result.premium_written,
            )
        except Exception:
            logger.exception("Failed to update %s", config.name)

    try:
        snapshot = upsert_dashboard_snapshot(build_dashboard_snapshot())
        logger.info(
            "Updated dashboard snapshot: generated_at=%s items=%d groups=%d",
            snapshot["generated_at_bj"],
            len(snapshot["items"]),
            len(snapshot["groups"]),
        )
    except Exception:
        logger.exception("Failed to update dashboard snapshot")


@app.timer_trigger(
    schedule="0 0 0,4,13 * * *",
    arg_name="timer",
    run_on_startup=False,
)
def update_regular(timer: func.TimerRequest) -> None:
    """Refresh data at Beijing 08:00, 12:00, and 21:00."""
    _refresh_recent_and_update_dashboard()


@app.timer_trigger(
    schedule="0 30 14 * * *",
    arg_name="timer",
    run_on_startup=False,
)
def update_late_evening(timer: func.TimerRequest) -> None:
    """Refresh data at Beijing 22:30."""
    _refresh_recent_and_update_dashboard()


@app.route(route="etfs", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def api_etfs(req: func.HttpRequest) -> func.HttpResponse:
    """Return all tracked ETFs with their latest premium record."""
    return _json_response([
        _etf_summary(config)
        for config in TRACKED_ETFS.values()
    ])


@app.route(route="dashboard", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def api_dashboard(req: func.HttpRequest) -> func.HttpResponse:
    """Return the latest precomputed dashboard snapshot."""
    snapshot = get_dashboard_snapshot()
    if not snapshot:
        return _json_response(
            {"error": "Dashboard snapshot is not available"},
            status_code=503,
        )
    return _json_response({
        "items": snapshot["items"],
        "groups": snapshot["groups"],
    })


@app.route(
    route="etfs/history",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def api_etf_history(req: func.HttpRequest) -> func.HttpResponse:
    """Return calculated premium history for one ETF."""
    code = req.params.get("code", "")
    config = TRACKED_ETFS.get(code)
    if not config:
        return _invalid_code_response(code)

    try:
        start = _date_param(req, "start")
        end = _date_param(req, "end")
    except ValueError:
        return _json_response(
            {"error": "Invalid date format; expected YYYY-MM-DD"},
            status_code=400,
        )

    records = get_premium_history(code, start_date=start, end_date=end)
    return _json_response({
        "code": config.code,
        "name": config.name,
        "short_name": config.short_name,
        "count": len(records),
        "data": records,
    })
