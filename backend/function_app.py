"""Azure Functions entry point for QDII ETF premium APIs."""

import json
import logging
import os
from datetime import date

import azure.functions as func

from shared.config import TRACKED_ETFS, EtfConfig
from shared.iopv import refresh_iopv
from shared.storage import (
    get_dashboard_snapshot,
    get_latest_premium,
    get_premium_history,
)

app = func.FunctionApp()

REVIEW_MODE_ENV = "REVIEW_MODE_ENABLED"


@app.timer_trigger(schedule="0 30 7,8,10 * * *", arg_name="timer", run_on_startup=False)
def collect_daily_iopv(timer: func.TimerRequest) -> None:
    """Collect at Beijing 15:30, 16:30 and 18:30 (Azure cron uses UTC)."""
    result = refresh_iopv()
    logging.info("IOPV collection: date=%s written=%s failed=%s skipped=%s",
                 result["date"], result.get("written", 0), result["failed"], result.get("skipped"))
    if result["failed"]:
        raise RuntimeError(f"IOPV collection exhausted retries: {result['failed']}")


def _json_response(body: object, status_code: int = 200) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(body, ensure_ascii=False, separators=(",", ":")),
        status_code=status_code,
        mimetype="application/json",
    )


def _review_mode_enabled() -> bool:
    value = os.environ.get(REVIEW_MODE_ENV, "")
    return value.strip().lower() in {"1", "true"}


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
        "fund_type": config.fund_type,
        "tracking_index": config.tracking_index,
        "tracking_index_name": config.tracking_index_name,
        "latest": get_latest_premium(config.code),
    }


@app.route(route="etfs", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def api_etfs(req: func.HttpRequest) -> func.HttpResponse:
    """Return all tracked ETFs with their latest premium record."""
    return _json_response([
        _etf_summary(config)
        for config in TRACKED_ETFS.values()
    ])


@app.route(route="review-mode", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def api_review_mode(req: func.HttpRequest) -> func.HttpResponse:
    """Return whether the Mini Program should use the review-safe UI."""
    return _json_response({"review_mode": _review_mode_enabled()})


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
        "fund_type": config.fund_type,
        "count": len(records),
        "data": records,
    })
