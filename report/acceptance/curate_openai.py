"""GUIDE 3.2 with raw curator evidence; uses only baseline learning records."""
import json
from pathlib import Path
from langchain_core.callbacks import BaseCallbackHandler, UsageMetadataCallbackHandler
from lab.curator import curate_skills, validate_skill
from lab.model import make_model


class Capture(BaseCallbackHandler):
    def on_chat_model_start(self, serialized, messages, **kwargs):
        self.prompt = "\n".join(str(m.content) for m in messages[0])

    def on_llm_end(self, response, **kwargs):
        self.response = response.generations[0][0].message.content


for task in ("code-learn", "data-learn", "logs-learn"):
    r = json.loads((Path("results/baseline") / task / "run.json").read_text())
    if r.get("error") or r.get("role") != "learn" or not r.get("total"):
        raise RuntimeError("Need completed learning baseline: " + task)
model = make_model()
capture, usage = Capture(), UsageMetadataCallbackHandler()
model.callbacks = [capture, usage]
paths = curate_skills(model=model)
out = Path("report/curator")
out.mkdir(parents=True, exist_ok=True)
(out / "prompt.txt").write_text(capture.prompt, encoding="utf-8")
(out / "response.txt").write_text(str(capture.response), encoding="utf-8")
(out / "run.json").write_text(json.dumps({"model": model.model_name, "usage": usage.usage_metadata,
    "paths": [str(p.relative_to(Path.cwd())) for p in paths], "calls": 1,
    "validation": {p.parent.name: validate_skill(p.read_text(), p.parent.name) for p in paths}}, indent=2), encoding="utf-8")
print("wrote " + str(paths), flush=True)
if not paths:
    raise RuntimeError("No valid skills: review raw output before retry")
