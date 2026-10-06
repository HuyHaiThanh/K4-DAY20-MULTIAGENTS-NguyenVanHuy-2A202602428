"""Additional offline tests; provided lab tests remain unchanged."""
import asyncio
import pytest
from lab.coordinator import Coordinator, CoordinatorException


class MockWorker:
    def __init__(self, name, delay=0, failures=0):
        self.name, self.delay, self.failures = name, delay, failures
        self.calls = 0
        self.cancelled = False

    async def process_async(self, content):
        self.calls += 1
        try:
            await asyncio.sleep(self.delay)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        if self.calls <= self.failures:
            raise RuntimeError("mock failure")
        return {"mock": True, "request": content}


def test_coordinator_init():
    worker = MockWorker("data_agent")
    coordinator = Coordinator(worker_agents=[worker])
    assert coordinator.workers[worker.name] is worker
    with pytest.raises(CoordinatorException):
        Coordinator(worker_agents=[worker, worker])


def test_parse_request():
    coordinator = Coordinator()
    assert coordinator.parse_request("Analyze sales data")["task_type"] == "data_analysis"
    assert coordinator.parse_request("Phân tích doanh thu và tạo biểu đồ")["task_type"] == "complex"
    assert coordinator.parse_request({"task_type": "evaluation", "content": "check", "parameters": {"path": "x"}})["parameters"] == {"path": "x"}
    for value in (None, "", "unknown", {"task_type": "bogus", "content": "x"}):
        with pytest.raises(CoordinatorException):
            coordinator.parse_request(value)


def test_route_task():
    coordinator = Coordinator(worker_agents=[MockWorker("data_agent"), MockWorker("code_agent")])
    assert coordinator.route_task("complex") == ["data_agent", "code_agent"]
    with pytest.raises(CoordinatorException):
        coordinator.route_task("evaluation")


def test_execute_tasks():
    async def scenario():
        slow = MockWorker("code_agent", delay=1)
        good = MockWorker("data_agent")
        coordinator = Coordinator(worker_agents=[good, slow])
        tasks = [{"id": "a", "worker": "data_agent", "content": "x"}, {"id": "b", "worker": "code_agent", "content": "y"}]
        results = await coordinator.execute_tasks(tasks, timeout=0.02)
        assert [r["status"] for r in results] == ["success", "timeout"]
        assert slow.cancelled and not coordinator.active_tasks
        with pytest.raises(CoordinatorException):
            await coordinator.execute_tasks([tasks[0], tasks[0]])
    asyncio.run(scenario())


def test_aggregate_results():
    coordinator = Coordinator()
    results = [{"status": "success", "type": "data", "content": 1}, {"status": "success", "type": "data", "content": 2}, {"status": "error", "error": "failure"}]
    response = coordinator.aggregate_results(results)
    assert response["status"] == "partial" and response["outputs"]["data"] == [1, 2]
    assert len(response["errors"]) == 1
    assert coordinator.aggregate_results([])["status"] == "error"


def test_retry_only_failed_workers():
    async def scenario():
        good, flaky = MockWorker("data_agent"), MockWorker("code_agent", failures=1)
        coordinator = Coordinator(worker_agents=[good, flaky])
        result = await coordinator.process_async("Analyze data and create report", max_retries=1)
        assert result["status"] == "success"
        assert good.calls == 1 and flaky.calls == 2
        assert not coordinator.active_tasks
    asyncio.run(scenario())


def test_capacity_and_cancellation():
    async def scenario():
        worker = MockWorker("data_agent", delay=1)
        coordinator = Coordinator(worker_agents=[worker], max_tasks=1)
        tasks = [{"id": "a", "worker": worker.name, "content": "x"}]
        running = asyncio.create_task(coordinator.execute_tasks(tasks))
        await asyncio.sleep(0.01)
        with pytest.raises(CoordinatorException):
            await coordinator.execute_tasks([{**tasks[0], "id": "b"}])
        running.cancel()
        with pytest.raises(asyncio.CancelledError):
            await running
        assert not coordinator.active_tasks and worker.cancelled
    asyncio.run(scenario())


def test_sync_and_async_entries():
    coordinator = Coordinator(worker_agents=[MockWorker("data_agent")])
    assert coordinator.process("Analyze data")["status"] == "success"
    async def scenario():
        with pytest.raises(CoordinatorException, match="process_async"):
            coordinator.process("Analyze data")
    asyncio.run(scenario())


def test_retry_exhaustion():
    async def scenario():
        worker = MockWorker("data_agent", failures=10)
        coordinator = Coordinator(worker_agents=[worker])
        results = await coordinator.execute_tasks_with_retry([{"id": "a", "worker": worker.name, "content": "x"}], max_retries=2)
        assert results[0]["status"] == "error" and results[0]["attempts"] == 3
    asyncio.run(scenario())


def test_workers_really_run_concurrently():
    async def scenario():
        entered = set()
        ready = asyncio.Event()
        class BarrierWorker:
            def __init__(self, name):
                self.name = name
            async def process_async(self, content):
                entered.add(self.name)
                if len(entered) == 2:
                    ready.set()
                await ready.wait()
                return self.name
        coordinator = Coordinator(worker_agents=[BarrierWorker("data_agent"), BarrierWorker("code_agent")])
        result = await coordinator.process_async("Analyze data and create report", timeout=0.5)
        assert result["status"] == "success" and len(entered) == 2
    asyncio.run(scenario())


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), True])
def test_invalid_timeout_is_rejected_before_execution(timeout):
    worker = MockWorker("data_agent")
    coordinator = Coordinator(worker_agents=[worker])
    with pytest.raises(CoordinatorException):
        asyncio.run(coordinator.execute_tasks([{"id": "x", "worker": worker.name, "content": "x"}], timeout))
    assert worker.calls == 0
