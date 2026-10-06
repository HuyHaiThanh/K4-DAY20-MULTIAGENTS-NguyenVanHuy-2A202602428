import asyncio
import pytest
from lab.system import MultiAgentSystem
from lab.benchmarking import Benchmark, percentile


def test_full_pipeline(tmp_path):
    result = asyncio.run(MultiAgentSystem(tmp_path).process("Analyze sales data and create chart"))
    assert result["status"] == "success" and result["data"]["revenue"] == 30
    assert result["evaluation"]["score"] == 85.5
    assert result["token_source"] == "synthetic" and result["token_usage"] > 0
    assert len(result["messages"]) == 6


def test_concurrent_requests(tmp_path):
    async def run():
        system = MultiAgentSystem(tmp_path)
        results = await asyncio.gather(*(system.process({"task_type": "data_analysis", "content": f"Task {i}"}) for i in range(10)))
        assert all(result["status"] == "success" for result in results)
        assert len({result["run_id"] for result in results}) == 10
    asyncio.run(run())


def test_invalid_request_and_empty_rows(tmp_path):
    async def run():
        system = MultiAgentSystem(tmp_path)
        for request in ("", {"task_type": "data_analysis", "content": "x", "parameters": {"rows": []}}):
            result = await system.process(request)
            assert result["status"] == "error" and result["error"]
    asyncio.run(run())


def test_benchmark_measures_real_samples(tmp_path):
    async def run():
        result = await Benchmark().run_test("data", "Analyze sales data", MultiAgentSystem(tmp_path), iterations=3)
        assert result["successes"] == 3 and result["error_rate"] == 0
        assert result["min"] <= result["median"] <= result["max"]
        assert result["provider_tokens"] == 0 and result["synthetic_tokens"] > 0
        assert len(result["samples"]) == 3 and result["throughput_requests_per_minute"] > 0
    asyncio.run(run())


def test_percentiles_even_samples():
    assert percentile([1, 2, 3, 4], .5) == 2.5
    assert percentile([1, 2, 3, 4], .99) == pytest.approx(3.97)
    with pytest.raises(ValueError):
        percentile([], .5)


def test_evaluator_terminal_tool_requires_valid_output(tmp_path):
    from lab.agents import EvaluatorAgent
    from lab.system import scripted
    result = {"score": 85.5, "feedback": "Supplied ratings", "issues": [], "suggestions": []}
    agent = EvaluatorAgent(scripted([("submit_evaluation", result)], "should not be called"), minimal=True)
    response = agent.process("Submit explicit evaluation")
    assert response["result"] == result and response["metadata"]["model_calls"] == 1
