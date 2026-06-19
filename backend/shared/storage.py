"""Azure Table Storage operations for QDII ETF premium data."""

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

TABLE_PRICE_HISTORY = "QDIIEtfPriceHistory"
TABLE_NAV_HISTORY = "QDIIEtfNavHistory"
TABLE_PREMIUM_HISTORY = "QDIIEtfPremiumHistory"
TABLE_DASHBOARD_SNAPSHOT = "QDIIEtfDashboardSnapshot"

DASHBOARD_PARTITION_KEY = "dashboard"
DASHBOARD_ROW_KEY = "latest"


def _get_connection_string() -> str:
    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")
    if not connection_string:
        raise RuntimeError(
            "AZURE_STORAGE_CONNECTION_STRING environment variable is not set"
        )
    return connection_string


def _get_table_client(table_name: str):
    from azure.data.tables import TableServiceClient

    service = TableServiceClient.from_connection_string(_get_connection_string())
    service.create_table_if_not_exists(table_name)
    return service.get_table_client(table_name)


def _beijing_now() -> str:
    beijing_tz = timezone(timedelta(hours=8))
    return datetime.now(beijing_tz).isoformat()


def _row_key(date_str: str) -> str:
    return date_str.replace("-", "")


def _drop_none(entity: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in entity.items() if value is not None}


def _upsert_entities(table_name: str, entities: list[dict[str, Any]]) -> int:
    from azure.core.exceptions import AzureError
    from azure.data.tables import UpdateMode

    table = _get_table_client(table_name)
    total = len(entities)
    print(f"Writing {total} records to {table_name}...", flush=True)

    if total == 0:
        logger.info("Upserted 0 entities into %s", table_name)
        return 0

    for index, entity in enumerate(entities, start=1):
        clean_entity = _drop_none(entity)
        for attempt in range(3):
            try:
                table.upsert_entity(clean_entity, mode=UpdateMode.MERGE)
                break
            except AzureError:
                if attempt == 2:
                    raise
                wait = (attempt + 1) * 2
                logger.warning("Storage upsert failed; retrying in %ds", wait)
                time.sleep(wait)

        if index % 100 == 0 or index == total:
            print(f"  {table_name}: {index}/{total}", flush=True)

    logger.info("Upserted %d entities into %s", total, table_name)
    return total


def upsert_price_history(etf_code: str, records: list[dict]) -> int:
    """Store raw unadjusted ETF daily price records."""
    fetched_at = _beijing_now()
    entities = [
        {
            "PartitionKey": etf_code,
            "RowKey": _row_key(record["date"]),
            "date_str": record["date"],
            "open": record.get("open"),
            "close": record["close"],
            "high": record.get("high"),
            "low": record.get("low"),
            "volume": record.get("volume"),
            "amount": record.get("amount"),
            "adjust": record.get("adjust", "none"),
            "source": record.get("source", "eastmoney_etf_daily_k"),
            "fetched_at_bj": fetched_at,
        }
        for record in records
    ]
    return _upsert_entities(TABLE_PRICE_HISTORY, entities)


def upsert_nav_history(etf_code: str, records: list[dict]) -> int:
    """Store raw ETF unit NAV records."""
    fetched_at = _beijing_now()
    entities = [
        {
            "PartitionKey": etf_code,
            "RowKey": _row_key(record["date"]),
            "date_str": record["date"],
            "nav": record["nav"],
            "daily_return_pct": record.get("daily_return_pct"),
            "source": record.get("source", "eastmoney_fund_nav"),
            "fetched_at_bj": fetched_at,
        }
        for record in records
    ]
    return _upsert_entities(TABLE_NAV_HISTORY, entities)


def upsert_premium_history(etf_code: str, records: list[dict]) -> int:
    """Store calculated close premium records."""
    computed_at = _beijing_now()
    entities = [
        {
            "PartitionKey": etf_code,
            "RowKey": _row_key(record["date"]),
            "date_str": record["date"],
            "close": record["close"],
            "nav": record["nav"],
            "premium_rate": record["premium_rate"],
            "computed_at_bj": computed_at,
        }
        for record in records
    ]
    return _upsert_entities(TABLE_PREMIUM_HISTORY, entities)


def _premium_record_from_entity(entity: dict[str, Any]) -> dict:
    return {
        "date": entity.get("date_str", entity["RowKey"]),
        "close": float(entity["close"]),
        "nav": float(entity["nav"]),
        "premium_rate": float(entity["premium_rate"]),
    }


def get_premium_history(
    etf_code: str,
    start_date: str = "",
    end_date: str = "",
) -> list[dict]:
    """Read calculated premium records sorted by date."""
    table = _get_table_client(TABLE_PREMIUM_HISTORY)
    filter_parts = [f"PartitionKey eq '{etf_code}'"]

    if start_date:
        filter_parts.append(f"RowKey ge '{_row_key(start_date)}'")
    if end_date:
        filter_parts.append(f"RowKey le '{_row_key(end_date)}'")

    entities = table.query_entities(" and ".join(filter_parts))
    records = [_premium_record_from_entity(entity) for entity in entities]
    records.sort(key=lambda r: r["date"])
    return records


def get_latest_premium(etf_code: str) -> dict | None:
    """Read the latest calculated premium record for one ETF."""
    records = get_premium_history(etf_code)
    if not records:
        return None
    return records[-1]


def upsert_dashboard_snapshot(payload: dict) -> dict:
    """Store the precomputed dashboard payload as the latest snapshot."""
    generated_at = payload.get("generated_at_bj") or _beijing_now()
    version = payload.get("version", "v1")
    payload_to_store = {
        **payload,
        "generated_at_bj": generated_at,
        "version": version,
    }
    entity = {
        "PartitionKey": DASHBOARD_PARTITION_KEY,
        "RowKey": DASHBOARD_ROW_KEY,
        "generated_at_bj": generated_at,
        "version": version,
        "payload_json": json.dumps(
            payload_to_store,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }
    _upsert_entities(TABLE_DASHBOARD_SNAPSHOT, [entity])
    return payload_to_store


def get_dashboard_snapshot() -> dict | None:
    """Read the latest precomputed dashboard payload."""
    from azure.core.exceptions import ResourceNotFoundError

    table = _get_table_client(TABLE_DASHBOARD_SNAPSHOT)
    try:
        entity = table.get_entity(
            partition_key=DASHBOARD_PARTITION_KEY,
            row_key=DASHBOARD_ROW_KEY,
        )
    except ResourceNotFoundError:
        return None

    payload = json.loads(entity["payload_json"])
    payload.setdefault("generated_at_bj", entity.get("generated_at_bj"))
    payload.setdefault("version", entity.get("version", "v1"))
    return payload
