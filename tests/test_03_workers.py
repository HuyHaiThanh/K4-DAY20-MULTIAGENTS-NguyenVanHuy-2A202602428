import asyncio
import json
import sqlite3
import pytest
from langchain_core.messages import AIMessage
from lab.testing import ScriptedChatModel
from lab.agents import DataAgent, CodeAgent, EvaluatorAgent
from lab.agents.tools import database_tool, restricted_python
from lab.communication import MessageQueue
from lab.coordinator import Coordinator


def fake(*messages):
    return ScriptedChatModel(script=list(messages))


def call(name, args, identifier="tool-1"):
    return {"name": name, "args": args, "id": identifier}


def test_data_agent_init():
    worker = DataAgent(fake(AIMessage(content="done")))
    assert worker.name == "data_agent"
    assert set(worker.tools) == {"csv_parser", "data_analysis", "data_validation"}


def test_data_agent_process():
    worker = DataAgent(fake(AIMessage(content="", tool_calls=[call("data_analysis", {
        "rows": [{"sales": "10"}, {"sales": "20"}], "column": "sales"})]), AIMessage(content="Sales total: 30")))
    response = worker.process("Analyze data")
    assert response["status"] == "success" and response["metadata"]["tools_used"] == 1
    assert worker._execute_tool("data_analysis", {"rows": [{"v": 3}, {"v": 5}], "column": "v", "operation": "avg"}) == {"all": 4}


def test_code_agent_process(tmp_path):
    worker = CodeAgent(fake(
        AIMessage(content="", tool_calls=[call("create_file", {"path": "sum.py", "content": "total = 10 + 20\nprint(total)"})]),
        AIMessage(content="", tool_calls=[call("run_script", {"path": "sum.py"}, "tool-2")]),
        AIMessage(content="Created and tested sum.py: 30")), tmp_path)
    response = worker.process("Create a script")
    assert response["status"] == "success" and response["metadata"]["tools_used"] == 2
    assert worker._execute_tool("run_script", {"path": "sum.py"})["stdout"] == "30"


def test_evaluator_agent():
    result = {"score": 90, "feedback": "Evidence checked", "issues": [], "suggestions": []}
    worker = EvaluatorAgent(fake(AIMessage(content="", tool_calls=[call("scoring", {
        "accuracy": 100, "completeness": 100, "clarity": 80, "performance": 70})]), AIMessage(content=json.dumps(result))))
    assert worker.process("Evaluate supplied output")["result"] == result
    assert worker._execute_tool("scoring", {"accuracy": 100, "completeness": 100, "clarity": 80, "performance": 70}) == {"score": 90}


def test_multiple_tool_calls_and_error():
    worker = DataAgent(fake(AIMessage(content="", tool_calls=[
        call("csv_parser", {"text": "a\n1\n"}), call("data_validation", {"rows": [{"a": "1"}], "required": ["a"]}, "tool-2")]), AIMessage(content="done")))
    assert worker.process("Analyze data")["metadata"]["tools_used"] == 2
    bad = DataAgent(fake(AIMessage(content="", tool_calls=[call("unknown", {})])))
    assert bad.process("Analyze data")["status"] == "error"


def test_budget_and_state_reset():
    message = AIMessage(content="", tool_calls=[call("csv_parser", {"text": "a\n1\n"})])
    worker = DataAgent(fake(message), max_steps=2)
    assert worker.process("Analyze data")["metadata"]["tools_used"] == 2
    assert worker.process("Analyze data")["metadata"]["tools_used"] == 2


@pytest.mark.parametrize("code", ["import os", "while True: pass", "print(open('secret'))", "print((1).__class__)", "print('x' * 100000)", "print(2 ** 100000)"])
def test_restricted_python_rejects_unsafe_code(code):
    with pytest.raises(ValueError):
        restricted_python(code)


def test_file_boundary_and_edit(tmp_path):
    worker = CodeAgent(fake(AIMessage(content="done")), tmp_path)
    assert worker._execute_tool("create_file", {"path": "../outside.py", "content": "x"})["status"] == "error"
    worker._execute_tool("create_file", {"path": "x.py", "content": "print(1)"})
    assert worker._execute_tool("create_file", {"path": "x.py", "content": "print(2)"})["status"] == "error"
    worker._execute_tool("edit_file", {"path": "x.py", "old": "1", "new": "2"})
    assert worker._execute_tool("run_script", {"path": "x.py"})["stdout"] == "2"


def test_readonly_database(tmp_path):
    path = tmp_path / "data.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE sales(value INTEGER)")
        connection.execute("INSERT INTO sales VALUES (7)")
    query = database_tool(path)
    assert query.invoke({"query": "SELECT sum(value) AS total FROM sales"}) == [{"total": 7}]
    for sql in ("DELETE FROM sales", "SELECT load_extension('x')", "SELECT 1; DROP TABLE sales"):
        with pytest.raises((ValueError, sqlite3.Error)):
            query.invoke({"query": sql})


def test_queue_copy_capacity_and_timeout():
    async def scenario():
        queue = MessageQueue(capacity=1)
        queue.register_agent("a")
        queue.register_agent("b")
        content = {"content": {"x": 1}, "correlation_id": "first"}
        await queue.send_message("a", "b", content)
        content["content"]["x"] = 2
        with pytest.raises(ValueError):
            await queue.send_message("a", "b", {})
        queue.register_agent("b")  # must not erase pending messages
        received = await queue.receive_message("b", correlation_id="first")
        assert received["content"]["x"] == 1 and "from" not in content
        history = queue.get_message_log()
        history[0]["content"]["x"] = 9
        assert queue.get_message_log()[0]["content"]["x"] == 1
        with pytest.raises(TimeoutError):
            await queue.receive_message("b", timeout=0.01)
    asyncio.run(scenario())


def test_queue_coordinator_out_of_order_and_worker_failure():
    async def scenario():
        class Worker:
            def __init__(self, name): self.name = name
            async def process_async(self, content):
                await asyncio.sleep(content["delay"])
                return {"status": "error", "error": "actual tool failure"} if content.get("fail") else content["value"]
        queue = MessageQueue()
        worker = Worker("data_agent")
        coordinator = Coordinator(worker_agents=[worker], message_queue=queue)
        results = await coordinator.execute_tasks([
            {"id": "slow", "worker": worker.name, "content": {"delay": 0.02, "value": "slow"}},
            {"id": "fast", "worker": worker.name, "content": {"delay": 0, "value": "fast"}},
            {"id": "bad", "worker": worker.name, "content": {"delay": 0, "fail": True}}])
        assert [r["content"] for r in results[:2]] == ["slow", "fast"]
        assert results[2]["status"] == "error"
        assert len(queue.get_message_log()) == 6
        assert all(not inbox for inbox in queue.queues.values())
    asyncio.run(scenario())


def test_queue_timeout_cleans_worker():
    async def scenario():
        cancelled = asyncio.Event()
        class Slow:
            name = "data_agent"
            async def process_async(self, content):
                try: await asyncio.sleep(10)
                finally: cancelled.set()
        queue = MessageQueue()
        coordinator = Coordinator(worker_agents=[Slow()], message_queue=queue)
        result = await coordinator.process_async("Analyze data", timeout=0.02)
        assert result["results"][0]["status"] == "timeout" and cancelled.is_set()
        assert not coordinator.active_tasks and all(not inbox for inbox in queue.queues.values())
    asyncio.run(scenario())


def test_invalid_evaluator_output():
    worker = EvaluatorAgent(fake(AIMessage(content="Everything looks good")))
    assert worker.process("Evaluate data")["status"] == "error"


def test_queue_direct_exchange_deadline_and_error():
    async def scenario():
        class Worker:
            name = "data_agent"
            async def process_async(self, content):
                if content == "error":
                    raise RuntimeError("worker failure")
                await asyncio.sleep(1)
        queue = MessageQueue()
        for content, exception in (("slow", TimeoutError), ("error", RuntimeError)):
            with pytest.raises(exception):
                    await queue.exchange("coordinator", Worker(), content, timeout=0.05 if content == "slow" else 1)
            assert all(not inbox for inbox in queue.queues.values())
    asyncio.run(scenario())


def test_data_dirty_input_and_tool_failure():
    worker = DataAgent(fake(AIMessage(content="", tool_calls=[call("data_analysis", {
        "rows": [{"value": "not-a-number"}], "column": "value"})])))
    assert worker.process("Analyze supplied data")["status"] == "error"
    with pytest.raises(ValueError):
        worker._execute_tool("csv_parser", {"text": "a,a\n1,2"})
    with pytest.raises(ValueError):
        worker._execute_tool("data_analysis", {"rows": [{"v": "NaN"}], "column": "v"})


def test_queue_real_worker_error_is_not_success():
    async def scenario():
        worker = DataAgent(fake(AIMessage(content="", tool_calls=[call("unknown", {})])))
        coordinator = Coordinator(worker_agents=[worker], message_queue=MessageQueue())
        result = await coordinator.process_async("Analyze data", max_retries=1)
        assert result["status"] == "error" and result["results"][0]["attempts"] == 2
        assert "Unknown tool" in result["results"][0]["error"]
    asyncio.run(scenario())
