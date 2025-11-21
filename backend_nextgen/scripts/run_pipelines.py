"""
Convenience script to run embedding and knowledge-graph pipelines on sample data.
"""

from __future__ import annotations

from pathlib import Path

from backend_nextgen.pipelines.embedding_pipeline import run_embedding_pipeline
from backend_nextgen.pipelines.knowledge_graph_pipeline import run_knowledge_graph_pipeline
from backend_nextgen.pipelines.metrics_pipeline import demo_metric_ingest


def main() -> None:
    base = Path(__file__).resolve().parents[1] / "data"
    sample_jsonl = base / "sample_products.jsonl"
    sample_csv = base / "sample_products.csv"
    run_embedding_pipeline(dataset_path=sample_jsonl)
    run_knowledge_graph_pipeline(csv_path=sample_csv)
    demo_metric_ingest()
    print("Pipelines executed successfully using sample data.")


if __name__ == "__main__":
    main()
