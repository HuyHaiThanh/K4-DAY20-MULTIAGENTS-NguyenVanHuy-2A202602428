"""Reproducible staged system for local and opt-in live acceptance runs."""
import asyncio
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import time
import math
import xml.etree.ElementTree as ET
from uuid import uuid4
from langchain_core.messages import AIMessage
from .agents import DataAgent, CodeAgent, EvaluatorAgent
from .communication import MessageQueue
from .coordinator import Coordinator
from .testing import ScriptedChatModel


def scripted(calls, final):
    return ScriptedChatModel(script=[*[AIMessage(content="", tool_calls=[{"name": name, "args": arguments, "id": f"tool-{index}"}])
                                       for index, (name, arguments) in enumerate(calls)], AIMessage(content=final)])


class MultiAgentSystem:
    """Fresh workers/models/workspace per request; dependencies run in stages.

    Offline decisions are scripted. Live model generation is explicitly enabled.
    Requests operate on a supplied/demo sales fixture, never invented external data.
    """
    def __init__(self, output_dir="report/acceptance/runs", *, live=False, stage_timeout=30, max_concurrent=10):
        self.output_dir = Path(output_dir)
        self.live = live
        self.stage_timeout = stage_timeout
        self.semaphore = asyncio.Semaphore(1 if live else max_concurrent)

    def _model(self, calls, final):
        if not self.live:
            return scripted(calls, final)
        from .model import make_model
        model = make_model()
        if hasattr(model, "max_retries"):
            model.max_retries = 0
        if hasattr(model, "request_timeout"):
            model.request_timeout = 20
        # ChatOpenAI has already built SDK clients in make_model(). Updating
        # model fields alone does not change their retry/timeout defaults.
        for name in ("root_client", "root_async_client"):
            client = getattr(model, name, None)
            if client is not None:
                client.max_retries = 0
                client.timeout = 20
        if hasattr(model, "max_tokens"):
            model.max_tokens = 700
        return model

    async def process(self, request, *, debug=False):
        async with self.semaphore:
            start = time.monotonic()
            run_id = uuid4().hex
            root = self.output_dir / run_id
            root.mkdir(parents=True, exist_ok=False)
            queue = MessageQueue()
            stages = {}
            record = {"run_id": run_id, "mode": "live" if self.live else "offline-scripted",
                      "status": "error", "request": request, "stages": stages, "error": None,
                      "token_usage": 0, "token_source": "provider" if self.live else "synthetic"}
            try:
                parsed = Coordinator().parse_request(request)
                kind = parsed["task_type"]
                rows = parsed["parameters"].get("rows", [{"month": "Jan", "sales": 10.0}, {"month": "Feb", "sales": 20.0}])
                if not isinstance(rows, list) or not 1 <= len(rows) <= 50:
                    raise ValueError("Supply 1-50 sales rows")
                normalized = [{"month": str(row["month"]), "sales": float(row["sales"])} for row in rows]
                if any(not math.isfinite(r["sales"]) or r["sales"] < 0 for r in normalized):
                    raise ValueError("Sales must be finite and nonnegative")
                coordinator = Coordinator(message_queue=queue)
                if kind in ("data_analysis", "complex"):
                    database = root / "sales.db"
                    with closing(sqlite3.connect(database)) as connection, connection:
                        connection.execute("CREATE TABLE sales(month TEXT, amount REAL)")
                        connection.executemany("INSERT INTO sales VALUES (?,?)", [(r["month"], r["sales"]) for r in normalized])
                    data = DataAgent(self._model([("query_database", {"query": "SELECT month, amount FROM sales ORDER BY rowid"})], "Queried supplied sales rows"), database, max_steps=4)
                    coordinator.workers[data.name] = data
                    stages["data"] = await coordinator.process_async({"task_type": "data_analysis", "content": "Use query_database to SELECT month, amount FROM sales ORDER BY rowid. Return the query results; do not invent data."}, timeout=self.stage_timeout)
                    if stages["data"]["status"] != "success":
                        raise ValueError("Data stage failed")
                    events = stages["data"]["results"][0]["content"]["metadata"]["tool_events"]
                    queried = next((e["output"]["data"] for e in events if e["name"] == "query_database" and e["output"].get("status") == "success"), None)
                    if queried is None:
                        raise ValueError("Model returned no verified database output")
                    expected_rows = [{"month": row["month"], "amount": row["sales"]} for row in normalized]
                    if queried != expected_rows:
                        raise ValueError("Database output does not match the supplied fixture")
                    normalized = [{"month": r["month"], "sales": r["amount"]} for r in queried]
                    record["data"] = {"rows": normalized, "revenue": sum(r["sales"] for r in normalized)}
                if kind in ("code_generation", "complex"):
                    chart_args = {"path": "sales_chart.svg", "labels": [r["month"] for r in normalized], "values": [float(r["sales"]) for r in normalized], "title": "Supplied sales"}
                    code_args = {"code": "print(" + " + ".join(str(r["sales"]) for r in normalized) + ")"}
                    code = CodeAgent(self._model([("create_visualization", chart_args), ("python_repl", code_args)], "Created chart and executed supplied total"), root, max_steps=4)
                    coordinator.workers[code.name] = code
                    stages["code"] = await coordinator.process_async({"task_type": "code_generation", "content": "Call create_visualization and python_repl with these exact arguments, then report verified outputs.", "parameters": {"chart": chart_args, "python": code_args}}, timeout=self.stage_timeout)
                    if stages["code"]["status"] != "success" or not (root / "sales_chart.svg").exists():
                        raise ValueError("Code stage failed or chart not created")
                    if not stages["code"]["results"][0]["content"]["metadata"].get("execution_verified"):
                        raise ValueError("Model did not execute Python verification")
                    code_events = stages["code"]["results"][0]["content"]["metadata"]["tool_events"]
                    if not any(e["name"] == "create_visualization" and e["input"].get("labels") == chart_args["labels"]
                               and e["input"].get("values") == chart_args["values"] for e in code_events):
                        raise ValueError("Chart inputs do not match verified data")
                    verified = any(e["name"] == "python_repl" and e["output"].get("status") == "success"
                                   and e["output"].get("stdout", "").strip() == str(sum(r["sales"] for r in normalized)) for e in code_events)
                    if not verified or ET.parse(root / "sales_chart.svg").getroot().tag != "{http://www.w3.org/2000/svg}svg":
                        raise ValueError("Independent code/chart check failed")
                    record["code"] = {"chart": str(root / "sales_chart.svg")}
                if kind in ("evaluation", "complex"):
                    supplied = parsed["parameters"].get("scores", {"accuracy": 85.0, "completeness": 90.0, "clarity": 80.0, "performance": 85.0})
                    from .tools import ScoringTool
                    weighted = ScoringTool().invoke({"scores": supplied})
                    if weighted["status"] != "success":
                        raise ValueError("Invalid supplied rubric")
                    final = {"score": weighted["weighted_score"], "feedback": "Weighted supplied ratings, not independent accuracy evidence", "issues": [], "suggestions": []}
                    evaluator = EvaluatorAgent(self._model([("score_result", {"scores": supplied}), ("submit_evaluation", final)], json.dumps(final)), workspace=root, minimal=True, max_steps=4)
                    coordinator.workers[evaluator.name] = evaluator
                    stages["evaluation"] = await coordinator.process_async({"task_type": "evaluation", "content": "Call score_result with supplied scores, then submit_evaluation using its weighted_score, feedback, issues, suggestions. Label score as supplied ratings.", "parameters": {"scores": supplied, "evidence": {"data": record.get("data"), "code": record.get("code")}}}, timeout=self.stage_timeout)
                    if stages["evaluation"]["status"] != "success":
                        raise ValueError("Evaluation stage failed")
                    record["evaluation"] = stages["evaluation"]["results"][0]["content"]["result"]
                    evaluation_events = stages["evaluation"]["results"][0]["content"]["metadata"]["tool_events"]
                    if not any(e["name"] == "score_result" for e in evaluation_events) or record["evaluation"]["score"] != weighted["weighted_score"]:
                        raise ValueError("Evaluator must use scoring tool and match independent rubric calculation")
                record["status"] = "success"
            except Exception as exc:
                record["error"] = f"{type(exc).__name__}: {exc}"
            finally:
                record["seconds"] = time.monotonic() - start
                record["tokens_complete"] = record["status"] == "success"
                record["messages"] = queue.get_message_log()
                worker_seconds = {}
                for stage in stages.values():
                    for result in stage["results"]:
                        worker_seconds[result["worker"]] = worker_seconds.get(result["worker"], 0) + result["seconds"]
                        content = result.get("content") or {}
                        record["token_usage"] += content.get("metadata", {}).get("tokens", {}).get("total", 0)
                record["worker_seconds"] = worker_seconds
                (root / "communication.jsonl").write_text("".join(json.dumps(message, ensure_ascii=False) + "\n" for message in record["messages"]), encoding="utf-8")
                (root / "run.json").write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
            return record
