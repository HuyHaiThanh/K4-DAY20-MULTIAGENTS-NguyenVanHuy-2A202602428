"""Common validated tool adapter with per-call timing and error envelopes."""
import asyncio
import logging
import time
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class BaseTool:
    name = "base_tool"
    description = "Validated local tool"
    schema = ToolInput

    def validate_input(self, input_dict):
        if not isinstance(input_dict, dict):
            raise ValueError("Tool input must be a dict")
        return self.schema.model_validate(input_dict).model_dump()

    def _execute(self, values):
        raise NotImplementedError

    def invoke(self, input_dict):
        start = time.monotonic()
        try:
            values = self.validate_input(input_dict)
            output = self._execute(values)
            seconds = round(time.monotonic() - start, 6)
            logging.getLogger(f"lab.tools.{self.name}").info("Tool success duration=%s", seconds)
            return {"status": "success", **output, "seconds": seconds}
        except Exception as exc:
            logging.getLogger(f"lab.tools.{self.name}").warning("Tool failed: %s", type(exc).__name__)
            return {"status": "error", "error": f"{type(exc).__name__}: {exc}", "seconds": round(time.monotonic() - start, 6)}

    async def ainvoke(self, input_dict):
        # Nonblocking adapter; tools must have their own bounded execution.
        return await asyncio.to_thread(self.invoke, input_dict)

    def as_langchain_tool(self):
        def execute(**kwargs):
            return self.invoke(kwargs)
        async def execute_async(**kwargs):
            return await self.ainvoke(kwargs)
        return StructuredTool(name=self.name, description=self.description, args_schema=self.schema,
                              func=execute, coroutine=execute_async)
