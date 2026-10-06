"""Actual local tool execution with scripted model decisions; zero API calls."""
import asyncio
import json
from pathlib import Path
import tempfile
from langchain_core.messages import AIMessage
from lab.testing import ScriptedChatModel
from lab.agents import DataAgent, CodeAgent, EvaluatorAgent
from lab.communication import MessageQueue
from lab.coordinator import Coordinator


def model(tool, args, final):
    return ScriptedChatModel(script=[AIMessage(content="", tool_calls=[{"name": tool, "args": args, "id": "local-tool"}]), AIMessage(content=final)])


async def main():
    with tempfile.TemporaryDirectory(prefix="worker-demo-") as directory:
        data = DataAgent(model("data_analysis", {"rows": [{"sales": 10}, {"sales": 20}], "column": "sales"}, "Verified total: 30"))
        code = CodeAgent(model("python_repl", {"code": "total = 10 + 20\nprint(total)"}, "Executed arithmetic: 30"), Path(directory))
        evaluator = EvaluatorAgent(model("scoring", {"accuracy": 100, "completeness": 100, "clarity": 100, "performance": 100}, json.dumps({"score": 100, "feedback": "Scripted demonstration, not independent quality evidence", "issues": [], "suggestions": []})))
        queue = MessageQueue()
        coordinator = Coordinator(worker_agents=[data, code, evaluator], message_queue=queue)
        result = await coordinator.process_async("Analyze data and create report")
        assert result["status"] == "success"
        assert all(r["content"]["metadata"]["tools_used"] == 1 for r in result["results"])
        assert result["results"][0]["content"]["metadata"]["tool_events"][0]["output"] == {"all": 30}
        assert result["results"][1]["content"]["metadata"]["tool_events"][0]["output"]["stdout"] == "30"
        evaluated = await coordinator.process_async({"task_type": "evaluation", "content": result})
        assert evaluated["status"] == "success" and len(queue.get_message_log()) == 6
        print(json.dumps({"model": "scripted-fake", "result": result, "evaluation": evaluated,
                          "messages": queue.get_message_log()}, indent=2, ensure_ascii=True))
        print("PASS: three workers, real local tools, six correlated queue messages; no API calls.")


if __name__ == "__main__":
    asyncio.run(main())
