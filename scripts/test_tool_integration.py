"""Offline staged collaboration with real SQLite, chart, scoring and report tools."""
import argparse
import asyncio
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
from contextlib import closing
from langchain_core.messages import AIMessage
from lab.testing import ScriptedChatModel
from lab.agents import DataAgent, CodeAgent, EvaluatorAgent
from lab.communication import MessageQueue
from lab.coordinator import Coordinator


def model(calls, final):
    messages = [AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"tool-{i}"}]) for i, (name, args) in enumerate(calls)]
    return ScriptedChatModel(script=[*messages, AIMessage(content=final)])


async def run(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tools-demo-") as directory:
        root = Path(directory)
        database = root / "sales.db"
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.execute("CREATE TABLE sales(month TEXT, year INTEGER, amount REAL)")
            connection.executemany("INSERT INTO sales VALUES (?,?,?)", [("Jan", 2026, 10), ("Feb", 2026, 20), ("Mar", 2025, 99)])
        queue = MessageQueue()
        data = DataAgent(model([("query_database", {"query": "SELECT month, amount FROM sales WHERE year=? ORDER BY month DESC", "parameters": [2026]})], "Queried 2026 sales"), database)
        coordinator = Coordinator(worker_agents=[data], message_queue=queue)
        stage1 = await coordinator.process_async({"task_type": "data_analysis", "content": "Query sales for 2026"})
        assert stage1["status"] == "success"
        rows = stage1["results"][0]["content"]["metadata"]["tool_events"][0]["output"]["data"]
        assert rows == [{"month": "Jan", "amount": 10.0}, {"month": "Feb", "amount": 20.0}]
        code = CodeAgent(model([
            ("create_visualization", {"path": "sales_chart.svg", "labels": [r["month"] for r in rows], "values": [r["amount"] for r in rows], "title": "Sales 2026"}),
            ("python_repl", {"code": "total = " + " + ".join(str(r["amount"]) for r in rows) + "\nprint(total)"})
        ], "Created SVG chart and verified total 30"), root)
        coordinator.workers[code.name] = code
        stage2 = await coordinator.process_async({"task_type": "code_generation", "content": "Visualize queried rows", "parameters": {"rows": rows}})
        assert stage2["status"] == "success" and (root / "sales_chart.svg").exists()
        assert stage2["results"][0]["content"]["metadata"]["tool_events"][1]["output"]["stdout"] == "30.0"
        scores = {"accuracy": 85.0, "completeness": 90.0, "clarity": 80.0, "performance": 85.0}
        evaluation = {"score": 85.5, "feedback": "Demonstration ratings, not an independent quality assessment", "issues": [], "suggestions": []}
        evaluator = EvaluatorAgent(model([
            ("score_result", {"scores": scores}),
            ("compare_results", {"actual": sum(r["amount"] for r in rows), "expected": 30.0}),
            ("generate_report", {"path": "evaluation.md", "title": "Local tool integration", "findings": ["SQLite returned 2 rows for 2026", "Created sales_chart.svg", "Executed total = 30.0", "Ratings are supplied demo values"], "evaluation": evaluation})
        ], json.dumps(evaluation)), workspace=root)
        coordinator.workers[evaluator.name] = evaluator
        stage3 = await coordinator.process_async({"task_type": "evaluation", "content": {"data": stage1, "code": stage2}})
        assert stage3["status"] == "success"
        score = stage3["results"][0]["content"]["metadata"]["tool_events"][0]["output"]
        assert score["weighted_score"] == 85.5 and score["grade"] == "B"
        assert len(queue.get_message_log()) == 6 and all(not inbox for inbox in queue.queues.values())
        for name in ("sales_chart.svg", "evaluation.md"):
            shutil.copyfile(root / name, output / name)
        trace = {"model": "scripted-fake", "data": stage1, "code": stage2, "evaluation": stage3, "messages": queue.get_message_log()}
        (output / "trace.json").write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
        print("1. DataAgent -> SQLite SELECT: PASS (2 actual rows)")
        print("2. CodeAgent -> SVG chart + child-process Python: PASS (total 30.0)")
        print("3. EvaluatorAgent -> weighted score + comparison + report: PASS (85.5/B, supplied demo ratings)")
        print(f"All tool integration scenarios passed (3/3). Artifacts: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="report/tools-demo")
    asyncio.run(run(parser.parse_args().output))
