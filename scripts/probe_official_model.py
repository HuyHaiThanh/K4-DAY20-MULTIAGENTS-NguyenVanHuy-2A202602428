"""Small tool-schema compatibility probe, independent of official tasks."""
import json
from langchain_core.tools import tool
from lab.model import make_model


@tool
def write_file(file_path: str, content: str) -> str:
    """Write content to a relative file_path. Probe only; never writes files."""
    return "probe"


model = make_model()
model.max_retries = 0
model.max_tokens = 512
reply = model.bind_tools([write_file], tool_choice="required").invoke("Call write_file with file_path workspace/probe.py and content print('hello').")
out = {"model": model.model_name, "tool_calls": reply.tool_calls, "usage": reply.usage_metadata}
print(json.dumps(out), flush=True)
assert reply.tool_calls and reply.tool_calls[0]["args"].get("file_path") == "workspace/probe.py"
