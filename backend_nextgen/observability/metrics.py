"""
Observability utilities for monitoring next-gen models.
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import sqlite3
import time


@dataclass
class MetricRecord:
    name: str
    value: float
    metadata: Dict[str, str]
    timestamp: float = time.time()


class MetricSink:
    """
    Lightweight SQLite-backed metric store to enable thesis experiments.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        if not self.db_path.parent.exists():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS metrics (
                    name TEXT,
                    value REAL,
                    metadata TEXT,
                    timestamp REAL
                )
                """
            )

    def log(self, record: MetricRecord) -> None:
        try:
            meta_str = json.dumps(record.metadata, ensure_ascii=False)
        except (TypeError, ValueError):
            meta_str = json.dumps({"raw": str(record.metadata)})
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO metrics (name, value, metadata, timestamp) VALUES (?, ?, ?, ?)",
                (record.name, record.value, meta_str, record.timestamp),
            )

    def query(self, name: str, since: float) -> List[MetricRecord]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT value, metadata, timestamp FROM metrics WHERE name = ? AND timestamp >= ?",
                (name, since),
            ).fetchall()
        records = []
        for row in rows:
            # Safe deserialization — never use eval() on stored data
            raw_meta = row[1]
            try:
                meta = json.loads(raw_meta)
            except (json.JSONDecodeError, TypeError):
                try:
                    meta = ast.literal_eval(raw_meta)
                except (ValueError, SyntaxError):
                    meta = {"raw": str(raw_meta)}
            records.append(
                MetricRecord(name=name, value=row[0], metadata=meta, timestamp=row[2])
            )
        return records
