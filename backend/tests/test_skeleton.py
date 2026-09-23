"""Day-1 skeleton gate (W1.5). Wave 2 owns test_rules/test_contradict/test_api."""

import pytest


def test_skeleton_boots():
    assert True


@pytest.mark.skip(
    reason="needs local stack (Ollama+Neo4j+PDF) — live suite lands in Wave 2"
)
def test_live_stack_placeholder():
    raise AssertionError("live test must stay skipped in CI")
