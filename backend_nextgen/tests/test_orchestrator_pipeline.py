from backend_nextgen.tests.conftest import DummyMetricRecord


def test_handle_query_returns_structured_payload(orchestrator_stub):
    result = orchestrator_stub.handle_query(
        "nike running shoes black size 10",
        user_context={"userId": "u1", "preferences": {}},
        limit=2,
        offset=0,
        history=["User: show me nike shoes"],
    )

    buckets = result["entities"]["entities"]
    assert buckets["BRAND"] == ["Nike"]
    assert buckets["COLOR"] == ["black"]
    assert len(result["items"]) == 2
    assert result["items"][0]["item_id"].startswith("ebay-")
    assert "recommendation" in result


def test_metrics_summary_reports_counts(orchestrator_stub):
    orchestrator_stub.metric_sink.log(DummyMetricRecord(name="nextgen_response_latency_ms", value=42.0))
    summary = orchestrator_stub.summarize_metrics(window_seconds=10)
    assert "metrics" in summary
    latency = summary["metrics"].get("response_latency_ms", {})
    assert latency.get("count", 0) >= 1
    assert "errors" in summary["metrics"]
