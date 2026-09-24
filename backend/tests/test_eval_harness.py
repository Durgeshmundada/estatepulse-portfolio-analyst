import pytest

from evals.run import load_cases, run_evaluation


@pytest.mark.asyncio
async def test_offline_eval_baseline_meets_quality_gates():
    report = await run_evaluation(load_cases(), "offline")
    summary = report["summary"]
    assert summary["cases"] == 14
    assert summary["pass_rate"] >= 0.95
    assert summary["intent_accuracy"] >= 0.95
    assert summary["groundedness_rate"] == 1
    assert summary["guardrail_pass_rate"] == 1
    assert summary["model_success_rate"] is None
