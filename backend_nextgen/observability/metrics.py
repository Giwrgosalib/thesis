"""
Observability utilities for monitoring next-gen models.
"""

from __future__ import annotations

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
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO metrics (name, value, metadata, timestamp) VALUES (?, ?, ?, ?)",
                (record.name, record.value, str(record.metadata), record.timestamp),
            )

    def query(self, name: str, since: float) -> List[MetricRecord]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT value, metadata, timestamp FROM metrics WHERE name = ? AND timestamp >= ?",
                (name, since),
            ).fetchall()
        return [
            MetricRecord(
                name=name,
                value=row[0],
                metadata=eval(row[1]),
                timestamp=row[2],
            )
            for row in rows
        ]
