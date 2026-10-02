#!/usr/bin/env python3

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from google.cloud import bigquery

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "lcf-monitor-legislativo")
DATASET = os.getenv("BQ_RAW_DATASET", "monitor_raw")

BASE = Path(__file__).resolve().parents[2]
DATA_DIR = BASE / "data" / "legislation"

client = bigquery.Client(project=PROJECT_ID)


def payload_hash(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def extract_records(payload):
    if isinstance(payload, list):
        return payload

    if not isinstance(payload, dict):
        return [payload]

    for key in (
        "proposicoes",
        "propositions",
        "items",
        "dados",
        "data",
    ):
        value = payload.get(key)
        if isinstance(value, list):
            return value

    return [payload]


def load_json_file(filename: str, table_name: str, source: str):
    path = DATA_DIR / filename

    if not path.exists():
        raise FileNotFoundError(path)

    payload = json.loads(path.read_text(encoding="utf-8"))
    records = extract_records(payload)

    now = datetime.now(timezone.utc).isoformat()

    rows = []

    for record in records:
        if not isinstance(record, dict):
            record = {"value": record}

        rows.append(
            {
                "source": source,
                "ingested_at": now,
                "payload_hash": payload_hash(record),
                "payload": record,
            }
        )

    table_id = f"{PROJECT_ID}.{DATASET}.{table_name}"

    job_config = bigquery.LoadJobConfig(
        schema=[
            bigquery.SchemaField("source", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("ingested_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("payload_hash", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("payload", "JSON", mode="REQUIRED"),
        ],
        write_disposition="WRITE_TRUNCATE",
    )

    job = client.load_table_from_json(
        rows,
        table_id,
        job_config=job_config,
    )

    job.result()

    print(f"{table_id}: {len(rows)} registro(s) carregado(s)")


if __name__ == "__main__":
    load_json_file(
        filename="propositions.json",
        table_name="propositions_raw",
        source="monitor_legislativo",
    )
