"""
Metric aggregation helpers for next-gen observability experiments.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Iterable

from backend_nextgen.observability.metrics import MetricSink, MetricRecord


def log_batch_metrics(metrics: Iterable[MetricRecord], db_path: Path | None = None) -> None:
    if db_path is None:
        db_path = Path("backend_nextgen/data/observability/metrics.db")
    sink = MetricSink(db_path)
    for record in metrics:
        sink.log(record)


def demo_metric_ingest() -> None:
    records = [
        MetricRecord(name="ner_latency_ms", value=12.5, metadata={"model": "deberta"}, timestamp=time.time()),
        MetricRecord(name="retriever_accuracy", value=0.82, metadata={"sample": "validation"}),
    ]
    log_batch_metrics(records)
