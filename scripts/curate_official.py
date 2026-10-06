"""Run the actual curator with provider usage and raw output evidence."""
import json
from pathlib import Path
from langchain_core.callbacks import BaseCallbackHandler, UsageMetadataCallbackHandler
from lab.curator import curate_skills
from lab.model import make_model


class Capture(BaseCallbackHandler):
    def on_chat_model_start(self, serialized, messages, **kwargs):
        self.prompt = "\n".join(str(m.content) for m in messages[0])

    def on_llm_end(self, response, **kwargs):
        self.response = response.generations[0][0].message.content


for task in ("code-learn", "data-learn", "logs-learn"):
    record = json.loads((Path("results/baseline") / task / "run.json").read_text())
    if record.get("error") or record.get("role") != "learn" or not record.get("total"):
        raise RuntimeError(f"Need a valid learning baseline first: {task}")

model = make_model()
model.model_name = "qwen/qwen3.8-27b"
model.max_tokens = 700
capture, usage = Capture(), UsageMetadataCallbackHandler()
model.callbacks = [capture, usage]
paths = curate_skills(model=model, max_skills=1)
out = Path("report/curator")
out.mkdir(exist_ok=True)
(out / "prompt.txt").write_text(getattr(capture, "prompt", ""), encoding="utf-8")
(out / "response.txt").write_text(str(getattr(capture, "response", "")), encoding="utf-8")
(out / "run.json").write_text(json.dumps({"model": model.model_name, "usage": usage.usage_metadata,
                                         "paths": [str(p.relative_to(Path.cwd())) for p in paths]}, indent=2), encoding="utf-8")
print("wrote " + str(paths), flush=True)
if not paths:
    raise RuntimeError("Curator generated no valid skills; review raw output")
