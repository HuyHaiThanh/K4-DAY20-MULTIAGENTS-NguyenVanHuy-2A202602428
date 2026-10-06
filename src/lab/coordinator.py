"""Offline coordinator extension; independent of the graded Deep Agents harness.

Workers implement ``name`` and async ``process_async(content)``. No model is
called: structured requests or conservative keyword routing are supported.
"""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import datetime, timezone
import logging
import math
import time
from uuid import uuid4
from typing import Protocol, Any


class Worker(Protocol):
    name: str

    async def process_async(self, content: Any) -> Any: ...


class CoordinatorException(ValueError):
    """Invalid request or coordinator configuration."""


class Coordinator:
    ROUTES = {
        "data_analysis": ("data_agent",),
        "code_generation": ("code_agent",),
        "evaluation": ("evaluator_agent",),
        "complex": ("data_agent", "code_agent"),
    }

    def __init__(self, model=None, worker_agents=(), message_queue=None, *, max_tasks=32):
        if isinstance(max_tasks, bool) or not isinstance(max_tasks, int) or max_tasks < 1:
            raise CoordinatorException("max_tasks must be a positive integer")
        self.model = model  # reserved for an explicitly enabled model parser
        self.workers = {}
        for worker in worker_agents:
            if not isinstance(worker.name, str) or not worker.name.strip() or worker.name in self.workers:
                raise CoordinatorException("Worker names must be nonempty and unique")
            if not callable(getattr(worker, "process_async", None)):
                raise CoordinatorException("Worker requires process_async")
            self.workers[worker.name] = worker
        self.task_queue = message_queue
        self.active_tasks = {}
        self.max_tasks = max_tasks
        self.logger = logging.getLogger("lab.coordinator")

    def parse_request(self, user_input):
        if isinstance(user_input, Mapping):
            request = dict(user_input)
            kind = request.get("task_type")
            content = request.get("content")
        elif isinstance(user_input, str) and user_input.strip():
            content = user_input.strip()
            text = content.casefold()
            data = any(word in text for word in ("data", "sales", "revenue", "dữ liệu", "doanh thu", "phân tích"))
            code = any(word in text for word in ("code", "chart", "plot", "report", "biểu đồ", "lập trình", "báo cáo"))
            review = any(word in text for word in ("evaluate", "review", "verify", "đánh giá", "kiểm tra"))
            kind = "complex" if data and code else "data_analysis" if data else "code_generation" if code else "evaluation" if review else None
            request = {}
        else:
            raise CoordinatorException("Request must be nonempty text or a mapping")
        if not isinstance(kind, str) or kind not in self.ROUTES:
            raise CoordinatorException("Unknown task type; provide an explicit task_type")
        if content is None or (isinstance(content, str) and not content.strip()):
            raise CoordinatorException("Request content is required")
        parameters = request.get("parameters", {})
        priority = request.get("priority", "normal")
        if not isinstance(parameters, Mapping) or priority not in ("low", "normal", "high"):
            raise CoordinatorException("Invalid parameters or priority")
        return {"task_type": kind, "content": content, "parameters": dict(parameters), "priority": priority}

    def route_task(self, task_type, content=None):
        if not isinstance(task_type, str) or task_type not in self.ROUTES:
            raise CoordinatorException("Unknown task type")
        names = list(self.ROUTES[task_type])
        missing = [name for name in names if name not in self.workers]
        if missing:
            raise CoordinatorException(f"Missing workers: {', '.join(missing)}")
        return names

    async def execute_tasks(self, tasks, timeout=60, *, max_retries=0):
        """Run workers concurrently with a per-attempt timeout and bounded retries.

        Retry is opt-in because workers with side effects must be idempotent.
        Successful tasks are never retried. Failed task outcomes remain visible.
        """
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
            raise CoordinatorException("timeout must be finite and positive")
        if isinstance(max_retries, bool) or not isinstance(max_retries, int) or max_retries < 0:
            raise CoordinatorException("max_retries must be a nonnegative integer")
        if not isinstance(tasks, (list, tuple)) or not tasks or len(tasks) + len(self.active_tasks) > self.max_tasks:
            raise CoordinatorException("Empty batch or task capacity exceeded")
        ids = set()
        for task in tasks:
            if not isinstance(task, Mapping):
                raise CoordinatorException("Each task must be a mapping")
            task_id = task.get("id")
            if not isinstance(task_id, str) or not task_id or task_id in ids or task_id in self.active_tasks:
                raise CoordinatorException("Task IDs must be nonempty and unique")
            worker = task.get("worker")
            if not isinstance(worker, str) or worker not in self.workers or "content" not in task:
                raise CoordinatorException("Unknown worker or missing content")
            ids.add(task_id)

        async def run(task):
            started = time.monotonic()
            outcome = {"id": task["id"], "worker": task["worker"], "type": task.get("type", task["worker"]), "content": None}
            try:
                for attempt in range(max_retries + 1):
                    outcome["attempts"] = attempt + 1
                    self.logger.info("task=%s worker=%s start attempt=%s", task["id"], task["worker"], attempt + 1)
                    try:
                        worker = self.workers[task["worker"]]
                        operation = (self.task_queue.exchange("coordinator", worker, task["content"], timeout)
                                     if self.task_queue is not None else worker.process_async(task["content"]))
                        value = await asyncio.wait_for(operation, timeout)
                        outcome["content"] = value
                        if isinstance(value, Mapping) and value.get("status") in ("error", "timeout"):
                            raise RuntimeError(value.get("error", "Worker reported failure"))
                        outcome.update(status="success", content=value, error=None)
                        break
                    except TimeoutError:
                        outcome.update(status="timeout", error="Worker exceeded timeout")
                    except Exception as exc:
                        outcome.update(status="error", error=f"{type(exc).__name__}: {exc}")
                    self.logger.warning("task=%s status=%s attempt=%s", task["id"], outcome["status"], attempt + 1)
            finally:
                outcome["seconds"] = round(time.monotonic() - started, 6)
                self.logger.info("task=%s end status=%s duration=%s", task["id"], outcome.get("status", "cancelled"), outcome["seconds"])
                self.active_tasks.pop(task["id"], None)
            return outcome

        handles = [asyncio.create_task(run(dict(task))) for task in tasks]
        self.active_tasks.update(zip((task["id"] for task in tasks), handles))
        try:
            return await asyncio.gather(*handles)
        finally:
            for handle in handles:
                if not handle.done():
                    handle.cancel()
            await asyncio.gather(*handles, return_exceptions=True)
            for task_id in ids:
                self.active_tasks.pop(task_id, None)

    async def execute_tasks_with_retry(self, tasks, max_retries=2, timeout=60):
        return await self.execute_tasks(tasks, timeout, max_retries=max_retries)

    def aggregate_results(self, results):
        results = list(results)
        successful = [result for result in results if result["status"] == "success"]
        status = "success" if results and len(successful) == len(results) else "partial" if successful else "error"
        grouped = {}
        for result in successful:
            grouped.setdefault(result["type"], []).append(result["content"])
        return {"status": status, "results": results, "outputs": grouped,
                "errors": [result for result in results if result["status"] != "success"],
                "timestamp": datetime.now(timezone.utc).isoformat()}

    async def process_async(self, user_input, *, timeout=60, max_retries=0):
        request = self.parse_request(user_input)
        workers = self.route_task(request["task_type"])
        request_id = uuid4().hex
        tasks = [{"id": f"request-{request_id}-{index}", "worker": name,
                  "type": name.removesuffix("_agent"), "content": request}
                 for index, name in enumerate(workers)]
        return self.aggregate_results(await self.execute_tasks(tasks, timeout, max_retries=max_retries))

    def process(self, user_input, **kwargs):
        """Synchronous entry point; use process_async inside an existing event loop."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.process_async(user_input, **kwargs))
        raise CoordinatorException("Use await process_async() inside an event loop")
