import pytest
import torch


@pytest.mark.parametrize(
    "history, refinement, expected_substring",
    [
        (["User: headphones"], "i want them black", "headphones black"),
        (["User: show me nike shoes"], "i want them black", "nike shoes black"),
        (
            ["User: show me nike shoes", "User: make them black"],
            "how about size 10",
            "nike shoes size 10",
        ),
    ],
)
def test_rewrite_keeps_anchor(history, refinement, expected_substring, orchestrator_stub, monkeypatch):
    # Force deterministic generation by lowering max length and temperature if supported.
    result = orchestrator_stub._rewrite_query_with_llm(refinement, history)
    assert any(
        token in result.lower() for token in expected_substring.lower().split()
    ), f"Rewrite '{result}' does not contain expected anchor/refinement: {expected_substring}"


def test_rewrite_falls_back_without_overlap(orchestrator_stub, monkeypatch):
    # Simulate a bad rewrite by monkeypatching the generator.
    class FakeGen:
        def generate(self, prompt):
            return "michael jackson in a suit"

    original_gen = orchestrator_stub.generator
    orchestrator_stub.generator = FakeGen()
    try:
        result = orchestrator_stub._rewrite_query_with_llm(
            "i want them black", ["User: headphones"]
        )
        assert "headphones" in result.lower()
        assert "black" in result.lower()
    finally:
        orchestrator_stub.generator = original_gen
