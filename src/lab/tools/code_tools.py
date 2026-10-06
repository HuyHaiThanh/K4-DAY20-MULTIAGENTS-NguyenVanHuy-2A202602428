import asyncio
import ast
from html import escape
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from pydantic import Field
from .base_tool import BaseTool, ToolInput
from lab.agents.tools import file_tools


class PythonInput(ToolInput):
    code: str = Field(min_length=1, max_length=10000)
    timeout: float = Field(default=30.0, gt=0, le=30, allow_inf_nan=False)


class PythonREPLTool(BaseTool):
    name = "python_repl"
    description = "Run bounded arithmetic Python in a child process with timeout, isolated request state and captured output; no imports/loops"
    schema = PythonInput

    def _environment(self):
        return {**{key: os.environ[key] for key in ("SystemRoot", "WINDIR", "TEMP", "TMP") if key in os.environ},
                "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}

    def _command(self):
        source = str(Path(__file__).resolve().parents[2])
        program = (
            "import sys,json; sys.path.insert(0," + repr(source) + "); "
            "from lab.agents.tools import restricted_python; "
            "r=restricted_python(json.load(sys.stdin)['code']); print(json.dumps(r))"
        )
        return [sys.executable, "-I", "-c", program]

    def validate_input(self, input_dict):
        values = super().validate_input(input_dict)
        tree = ast.parse(values["code"])
        if sum(1 for _ in ast.walk(tree)) > 500:
            raise ValueError("Code exceeds AST budget")
        return values

    def _decode(self, completed):
        if completed.returncode:
            raise ValueError(completed.stderr[-2000:] or "Child process failed")
        result = json.loads(completed.stdout)
        result["stdout"] = result["stdout"][:10000]
        return {**result, "stderr": "", "isolated_process": True}

    def _execute(self, values):
        completed = subprocess.run(self._command(), input=json.dumps({"code": values["code"]}),
                                   capture_output=True, text=True, encoding="utf-8", env=self._environment(), timeout=values["timeout"])
        return self._decode(completed)

    async def ainvoke(self, input_dict):
        start = time.monotonic()
        process = None
        communication = None
        try:
            values = self.validate_input(input_dict)
            # Standard pipes work on Windows hosts where asyncio's named pipes
            # are denied. Only bounded Popen startup runs on the event-loop thread.
            process = subprocess.Popen(self._command(), stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", env=self._environment())
            communication = asyncio.create_task(asyncio.to_thread(process.communicate, json.dumps({"code": values["code"]})))
            async with asyncio.timeout(values["timeout"]):
                stdout, stderr = await asyncio.shield(communication)
            completed = subprocess.CompletedProcess([], process.returncode, stdout, stderr)
            return {"status": "success", **self._decode(completed), "seconds": round(time.monotonic() - start, 6)}
        except Exception as exc:
            return {"status": "error", "error": f"{type(exc).__name__}: {exc}", "seconds": round(time.monotonic() - start, 6)}
        finally:
            if process is not None and process.returncode is None:
                process.kill()
            if communication is not None:
                await asyncio.shield(communication)


class FileInput(ToolInput):
    path: str = Field(min_length=1, max_length=240)
    content: str = Field(max_length=100000)


class CreateFileTool(BaseTool):
    name = "create_file"
    description = "Create a new bounded UTF-8 file strictly inside workspace; never overwrite"
    schema = FileInput
    def __init__(self, base_path):
        self._tool = file_tools(base_path)[0]
    def _execute(self, values):
        return self._tool.invoke(values)


class EditInput(ToolInput):
    path: str = Field(min_length=1, max_length=240)
    old: str = Field(min_length=1, max_length=100000)
    new: str = Field(max_length=100000)


class EditFileTool(CreateFileTool):
    name = "edit_file"
    description = "Replace exactly one matching occurrence inside a bounded workspace file"
    schema = EditInput
    def __init__(self, base_path):
        self._tool = file_tools(base_path)[1]


class ScriptInput(ToolInput):
    path: str = Field(min_length=1, max_length=240)
    timeout: float = Field(default=30.0, gt=0, le=30, allow_inf_nan=False)


class RunScriptTool(PythonREPLTool):
    name = "run_script"
    description = "Run a workspace file with the restricted Python child process and timeout"
    schema = ScriptInput
    def __init__(self, base_path):
        self.root = Path(base_path).resolve(strict=True)
    def validate_input(self, input_dict):
        values = BaseTool.validate_input(self, input_dict)
        path = Path(values["path"])
        resolved = (self.root / path).resolve(strict=True)
        if path.is_absolute() or path.drive or not resolved.is_relative_to(self.root) or resolved.stat().st_size > 10000:
            raise ValueError("Invalid script path or size")
        code = resolved.read_text(encoding="utf-8")
        if sum(1 for _ in ast.walk(ast.parse(code))) > 500:
            raise ValueError("Code exceeds AST budget")
        return PythonInput.model_validate({"code": code, "timeout": values["timeout"]}).model_dump()


class ChartInput(ToolInput):
    path: str = Field(min_length=1, max_length=240)
    labels: list[str] = Field(min_length=1, max_length=50)
    values: list[float] = Field(min_length=1, max_length=50)
    title: str = Field(default="Sales", max_length=200)


class VisualizationTool(CreateFileTool):
    name = "create_visualization"
    description = "Create an SVG bar chart from supplied nonnegative values, no matplotlib or arbitrary code"
    schema = ChartInput
    def _execute(self, values):
        labels, amounts = values["labels"], values["values"]
        if len(labels) != len(amounts) or any(len(label) > 100 for label in labels) or any(not math.isfinite(v) or v < 0 for v in amounts):
            raise ValueError("Invalid labels or chart values")
        if not values["path"].endswith(".svg"):
            raise ValueError("Chart path must end in .svg")
        width = max(600, len(labels) * 70)
        maximum = max(amounts) or 1
        parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="360" viewBox="0 0 {width} 360">',
                 '<rect width="100%" height="100%" fill="white"/>', f'<text x="30" y="30" font-size="20">{escape(values["title"])}</text>']
        for i, (label, amount) in enumerate(zip(labels, amounts)):
            height = 240 * amount / maximum
            x = 40 + i * (width - 80) / len(labels)
            parts.extend([f'<rect x="{x}" y="{290-height}" width="{(width-80)/len(labels)-10}" height="{height}" fill="#2563eb"/>',
                          f'<text x="{x}" y="315" font-size="12">{escape(label)}</text>',
                          f'<text x="{x}" y="{280-height}" font-size="12">{amount:g}</text>'])
        parts.append('</svg>')
        return self._tool.invoke({"path": values["path"], "content": "\n".join(parts)})
