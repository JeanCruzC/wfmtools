import json
import os
import sqlite3
from pathlib import Path
from typing import Any

DATABASE_PATH = os.getenv("DATABASE_PATH", "/data/app.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS call_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mes INTEGER NOT NULL,
                fecha INTEGER NOT NULL,
                semana TEXT NOT NULL,
                hora INTEGER NOT NULL CHECK (hora >= 0 AND hora <= 23),
                recibidas INTEGER NOT NULL DEFAULT 0,
                atendidas INTEGER NOT NULL DEFAULT 0,
                abandonada INTEGER NOT NULL DEFAULT 0,
                atendidas_sla INTEGER NOT NULL DEFAULT 0,
                aht_seg REAL NOT NULL DEFAULT 0,
                tme_seg REAL NOT NULL DEFAULT 0,
                dia_sem INTEGER NOT NULL CHECK (dia_sem >= 1 AND dia_sem <= 7),
                source TEXT DEFAULT 'manual',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_records_mes ON call_records(mes);
            CREATE INDEX IF NOT EXISTS idx_records_semana ON call_records(semana);
            CREATE INDEX IF NOT EXISTS idx_records_dia ON call_records(dia_sem);
            CREATE INDEX IF NOT EXISTS idx_records_hora ON call_records(hora);

            CREATE TABLE IF NOT EXISTS scenarios (
                kind TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )


def load_json_file(path: str | Path) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def upsert_scenario(kind: str, name: str, payload: dict[str, Any]) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO scenarios(kind, name, payload_json, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(kind) DO UPDATE SET
                name = excluded.name,
                payload_json = excluded.payload_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (kind, name, json.dumps(payload, ensure_ascii=False)),
        )


def get_scenario(kind: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT kind, name, payload_json, updated_at FROM scenarios WHERE kind = ?",
            (kind,),
        ).fetchone()
    if not row:
        return None
    return {
        "kind": row["kind"],
        "name": row["name"],
        "payload": json.loads(row["payload_json"]),
        "updated_at": row["updated_at"],
    }
