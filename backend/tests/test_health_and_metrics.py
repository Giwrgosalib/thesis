import os
from pathlib import Path


def test_health_endpoint_reports_healthy(client):
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "healthy"
    assert "services" in payload
    assert "database" in payload["services"]


def test_metrics_endpoint_uses_local_data(monkeypatch, client, tmp_path):
    # Create isolated data folder with small fixtures.
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    (data_dir / "feedback_log.csv").write_text("rating\n5\n4\n3\n", encoding="utf-8")
    (data_dir / "refined_balanced_dataset.csv").write_text(
        "intent,text\nsearch_product,iphone 15 pro\n", encoding="utf-8"
    )

    # Force metrics module to read from the temporary folder.
    monkeypatch.chdir(tmp_path)

    response = client.get("/metrics")
    assert response.status_code == 200
    payload = response.get_json()

    assert payload["feedback_metrics"]["total_feedback"] == 3
    assert payload["user_metrics"]["status"] in {"no_collection", "empty"}
    assert payload["dataset_metrics"]["total_samples"] == 1
