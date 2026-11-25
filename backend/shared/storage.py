"""Azure Table Storage operations for exchange-traded QDII fund data."""

import json
import logging
import math
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

TABLE_PRICE_HISTORY = "QDIIEtfPriceHistory"
TABLE_NAV_HISTORY = "QDIIEtfNavHistory"
TABLE_PREMIUM_HISTORY = "QDIIEtfPremiumHistory"
TABLE_DASHBOARD_SNAPSHOT = "QDIIEtfDashboardSnapshot"
TABLE_IOPV_HISTORY = "QDIIEtfIopvHistory"
HISTORY_TABLES = (TABLE_PRICE_HISTORY, TABLE_NAV_HISTORY, TABLE_PREMIUM_HISTORY)
BUSINESS_TABLES = (*HISTORY_TABLES, TABLE_DASHBOARD_SNAPSHOT)

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

    partitions = defaultdict(list)
    for entity in entities:
        partitions[entity["PartitionKey"]].append(_drop_none(entity))
    written = 0
    for partition in partitions.values():
        for offset in range(0, len(partition), 100):
            batch = partition[offset:offset + 100]
            operations = [("upsert", entity, {"mode": UpdateMode.REPLACE}) for entity in batch]
            for attempt in range(3):
                try:
                    table.submit_transaction(operations)
                    break
                except AzureError:
                    if attempt == 2:
                        raise
                    time.sleep((attempt + 1) * 2)
            written += len(batch)
            print(f"  {table_name}: {written}/{total}", flush=True)

    logger.info("Upserted %d entities into %s", total, table_name)
    return total


def upsert_price_history(etf_code: str, records: list[dict]) -> int:
    """Store raw unadjusted exchange-traded fund daily price records."""
    fetched_at = _beijing_now()
    entities = [
        {
            "PartitionKey": etf_code,
            "RowKey": _row_key(record["date"]),
            "date_str": record["date"],
            "close": record["close"],
            "adjust": record["adjust"],
            "source": record["source"],
            "fetched_at_bj": fetched_at,
        }
        for record in records
    ]
    return _upsert_entities(TABLE_PRICE_HISTORY, entities)


def upsert_nav_history(etf_code: str, records: list[dict]) -> int:
    """Store raw fund unit NAV records."""
    fetched_at = _beijing_now()
    entities = [
        {
            "PartitionKey": etf_code,
            "RowKey": _row_key(record["date"]),
            "date_str": record["date"],
            "nav": record["nav"],
            "source": record["source"],
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
            "nav_date": record["nav_date"],
            "premium_basis": record["premium_basis"],
            "computed_at_bj": computed_at,
        }
        for record in records
    ]
    return _upsert_entities(TABLE_PREMIUM_HISTORY, entities)


def _premium_record_from_entity(entity: dict[str, Any]) -> dict:
    return {
        "date": entity["date_str"],
        "close": float(entity["close"]),
        "nav": float(entity["nav"]),
        "iopv": None,
        "premium_rate": float(entity["premium_rate"]),
        "nav_date": entity["nav_date"],
        "premium_basis": entity["premium_basis"],
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
    records = {record["date"]: record for record in map(_premium_record_from_entity, entities)}
    iopv_table = _get_table_client(TABLE_IOPV_HISTORY)
    for entity in iopv_table.query_entities(" and ".join(filter_parts)):
        close, iopv = entity.get("close"), entity.get("iopv")
        if not all(isinstance(value, (int, float)) and not isinstance(value, bool)
                   and math.isfinite(value) and value > 0 for value in (close, iopv)):
            continue
        day = entity["date_str"]
        records[day] = {"date": day, "close": float(close), "iopv": float(iopv),
                        "nav": None, "nav_date": None, "premium_basis": "iopv",
                        "premium_rate": close / iopv - 1}
    return [records[day] for day in sorted(records)]


def upsert_iopv_history(records: list[dict]) -> int:
    """Keep one successfully collected IOPV quote per fund and trading date."""
    entities = [{"PartitionKey": row["code"], "RowKey": _row_key(row["date"]),
                 "date_str": row["date"], "close": row["close"], "iopv": row["iopv"],
                 "source": row["source"], "quote_at_bj": row["quote_at_bj"],
                 "fetched_at_bj": row["fetched_at_bj"]} for row in records]
    if not entities:
        return 0
    return _upsert_entities(TABLE_IOPV_HISTORY, entities)


def get_latest_premium(etf_code: str) -> dict | None:
    """Read the latest calculated premium record for one ETF."""
    records = get_premium_history(etf_code)
    if not records:
        return None
    return records[-1]


def read_entities(table_name: str, code: str = "") -> list[dict]:
    """Read only the application's business tables."""
    if table_name not in BUSINESS_TABLES:
        raise ValueError(f"Not a business table: {table_name}")
    table = _get_table_client(table_name)
    if code:
        return list(table.query_entities("PartitionKey eq @code", parameters={"code": code}))
    return list(table.list_entities())


def reset_history() -> dict[str, int]:
    """Delete all business entities without backing up or dropping tables."""
    counts = {}
    for name in (TABLE_DASHBOARD_SNAPSHOT, TABLE_PREMIUM_HISTORY, TABLE_NAV_HISTORY, TABLE_PRICE_HISTORY):
        table = _get_table_client(name)
        partitions = defaultdict(list)
        for entity in table.list_entities(select=["PartitionKey", "RowKey"]):
            partitions[entity["PartitionKey"]].append({
                "PartitionKey": entity["PartitionKey"], "RowKey": entity["RowKey"],
            })
        counts[name] = 0
        for partition in partitions.values():
            for offset in range(0, len(partition), 100):
                batch = partition[offset:offset + 100]
                table.submit_transaction([("delete", entity) for entity in batch])
                counts[name] += len(batch)
            print(f"Deleted {counts[name]} from {name}", flush=True)
        if next(iter(table.list_entities(select=["RowKey"])), None) is not None:
            raise RuntimeError(f"Table is not empty after reset: {name}")
    return counts


def upsert_dashboard_snapshot(payload: dict) -> dict:
    """Store the precomputed dashboard payload as the latest snapshot."""
    generated_at = payload.get("generated_at_bj") or _beijing_now()
    payload_to_store = {
        **payload,
        "generated_at_bj": generated_at,
    }
    entity = {
        "PartitionKey": DASHBOARD_PARTITION_KEY,
        "RowKey": DASHBOARD_ROW_KEY,
        "generated_at_bj": generated_at,
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
    return payload
