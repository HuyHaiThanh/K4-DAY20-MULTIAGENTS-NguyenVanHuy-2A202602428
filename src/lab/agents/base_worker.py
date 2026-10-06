"""Bounded tool-calling worker; tests supply a fake chat model."""
import asyncio
from collections.abc import Mapping
import json
import logging
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage


class BaseWorker:
    def __init__(self, name, model, tools, *, max_steps=8, max_tool_calls=32):
        if any(isinstance(v, bool) or not isinstance(v, int) or v < 1 for v in (max_steps, max_tool_calls)):
            raise ValueError("Worker limits must be positive integers")
        self.name = name
        self.tools = {tool.name: tool for tool in tools}
        if len(self.tools) != len(tools):
            raise ValueError("Duplicate tool names")
        self.model = model.bind_tools(list(self.tools.values()))
        self.system_prompt = "Use only available tools and report verified results."
        self.max_steps, self.max_tool_calls = max_steps, max_tool_calls
        self.logger = logging.getLogger(f"lab.{name}")

    def _build_prompt(self, task_content, parameters=None):
        if isinstance(task_content, Mapping) and "content" in task_content:
            parameters = task_content.get("parameters", {}) if parameters is None else parameters
            task_content = task_content["content"]
        if task_content is None or (isinstance(task_content, str) and not task_content.strip()):
            raise ValueError("Task content is required")
        if parameters is not None and not isinstance(parameters, Mapping):
            raise ValueError("Parameters must be a mapping")
        return [SystemMessage(content=self.system_prompt), HumanMessage(content=json.dumps(
            {"task": task_content, "parameters": dict(parameters or {})}, ensure_ascii=False))]

    def _execute_tool(self, tool_name, tool_input):
        if tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}")
        return self.tools[tool_name].invoke(tool_input)

    async def process_async(self, task_content, parameters=None):
        executed = []  # per-request state: concurrent calls do not share counters
        events = []
        try:
            messages = self._build_prompt(task_content, parameters)
            for step in range(self.max_steps):
                response = await self.model.ainvoke(messages)
                messages.append(response)
                if not response.tool_calls:
                    return {"status": "success", "result": response.content,
                            "metadata": {"tools_used": len(executed), "tool_names": executed, "tool_events": events, "model_calls": step + 1}}
                for call in response.tool_calls:
                    if len(executed) >= self.max_tool_calls:
                        raise ValueError("Tool-call budget exhausted")
                    if call["name"] not in self.tools:
                        raise ValueError(f"Unknown tool: {call['name']}")
                    arguments = call.get("args", call.get("input", {}))
                    result = await self.tools[call["name"]].ainvoke(arguments)
                    executed.append(call["name"])
                    events.append({"name": call["name"], "id": call["id"], "input": arguments, "output": result})
                    if isinstance(result, dict) and result.get("status") == "error":
                        raise ValueError(result.get("error", "Tool reported failure"))
                    messages.append(ToolMessage(content=json.dumps(result, ensure_ascii=False), tool_call_id=call["id"]))
            raise ValueError("Model-step budget exhausted")
        except Exception as exc:
            self.logger.warning("Worker failed: %s", type(exc).__name__)
            return {"status": "error", "error": f"{type(exc).__name__}: {exc}", "result": None,
                    "metadata": {"tools_used": len(executed), "tool_names": executed, "tool_events": events}}

    def process(self, task_content, parameters=None):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.process_async(task_content, parameters))
        raise ValueError("Use await process_async inside an event loop")
