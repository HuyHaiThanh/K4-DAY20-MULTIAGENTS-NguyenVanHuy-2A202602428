import asyncio
import json
import sqlite3
import sys
from contextlib import closing
import pytest
from lab.tools import (QueryDatabaseTool, PythonREPLTool, CreateFileTool, EditFileTool,
                       RunScriptTool, ScoringTool, ValidationTool, ComparisonTool,
                       ReportGeneratorTool, VisualizationTool, CSVParserTool, AggregationTool)


def test_query_database_tool(tmp_path):
    database = tmp_path / "sales.db"
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute("CREATE TABLE sales(year INTEGER, amount REAL)")
        connection.executemany("INSERT INTO sales VALUES (?,?)", [(2026, 10), (2026, 20)])
    query = QueryDatabaseTool(database)
    result = query.invoke({"query": "SELECT amount FROM sales WHERE year=? LIMIT 2", "parameters": [2026], "limit": 1})
    assert result["status"] == "success" and result["data"] == [{"amount": 10.0}] and result["truncated"]
    for sql in ("DELETE FROM sales", "SELECT load_extension('x')", "SELECT 1; DROP TABLE sales"):
        assert query.invoke({"query": sql})["status"] == "error"
    assert query.invoke({"query": "SELECT randomblob(10000000)"})["status"] == "error"
    assert query.invoke({"query": "SELECT 1", "limit": -1})["status"] == "error"


def test_python_repl_tool():
    repl = PythonREPLTool()
    result = repl.invoke({"code": "total = 10 + 20\nprint(total)"})
    assert result["status"] == "success" and result["stdout"] == "30" and result["isolated_process"]
    assert repl.invoke({"code": "print(total)"})["status"] == "error"  # no shared state
    assert repl.invoke({"code": "import os"})["status"] == "error"


def test_create_file_tool(tmp_path):
    create = CreateFileTool(tmp_path)
    assert create.invoke({"path": "a.py", "content": "print(3)"})["status"] == "success"
    assert create.invoke({"path": "a.py", "content": "print(4)"})["status"] == "error"
    assert create.invoke({"path": "../escape", "content": "x"})["status"] == "error"
    assert EditFileTool(tmp_path).invoke({"path": "a.py", "old": "3", "new": "4"})["status"] == "success"
    assert RunScriptTool(tmp_path).invoke({"path": "a.py"})["stdout"] == "4"


def test_scoring_tool():
    result = ScoringTool().invoke({"scores": {"accuracy": 85.0, "completeness": 90.0, "clarity": 80.0, "performance": 85.0}})
    assert result["weighted_score"] == 85.5 and result["grade"] == "B"
    for values in ({"scores": {}}, {"scores": {"a": 50.0}, "criteria": {"a": 0.0}}, {"scores": {"a": float("nan")}, "criteria": {"a": 1.0}}):
        assert ScoringTool().invoke(values)["status"] == "error"


def test_validation_comparison_and_report(tmp_path):
    assert not ValidationTool().invoke({"result": {}, "required": ["score"]})["valid"]
    assert ComparisonTool().invoke({"actual": True, "expected": 1})["matches"] is False
    report = ReportGeneratorTool(tmp_path).invoke({"path": "report.md", "title": "Evaluation", "findings": ["Verified total 30"], "evaluation": {"score": 85.5}})
    assert report["status"] == "success" and "Verified total 30" in (tmp_path / "report.md").read_text()


def test_chart_and_data_tools(tmp_path):
    parsed = CSVParserTool().invoke({"text": "month,sales\nJan,10\nFeb,20\n"})
    assert AggregationTool().invoke({"rows": parsed["data"], "column": "sales"})["data"] == {"all": 30}
    chart = VisualizationTool(tmp_path).invoke({"path": "sales.svg", "labels": ["Jan", "Feb"], "values": [10.0, 20.0], "title": "<Sales>"})
    assert chart["status"] == "success" and "&lt;Sales&gt;" in (tmp_path / "sales.svg").read_text()
    assert VisualizationTool(tmp_path).invoke({"path": "bad.svg", "labels": ["Jan"], "values": [-1.0]})["status"] == "error"


def test_python_timeout_and_cancel_reap_child(monkeypatch):
    async def scenario():
        repl = PythonREPLTool()
        from lab.tools import code_tools
        original = code_tools.subprocess.Popen
        children = []
        def capture(*args, **kwargs):
            child = original(*args, **kwargs)
            children.append(child)
            return child
        monkeypatch.setattr(code_tools.subprocess, "Popen", capture)
        monkeypatch.setattr(repl, "_command", lambda: [sys.executable, "-I", "-c", "import time; time.sleep(10)"])
        result = await repl.ainvoke({"code": "print(1)", "timeout": 0.1})
        assert result["status"] == "error" and "TimeoutError" in result["error"]
        assert children[0].poll() is not None
        task = asyncio.create_task(repl.ainvoke({"code": "print(1)"}))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert all(child.poll() is not None for child in children)
    asyncio.run(scenario())
