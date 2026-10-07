"""Record the common factory configuration without printing credentials or calling API."""
import json
import platform
from importlib.metadata import version
from pathlib import Path
from lab.model import make_model

model = make_model()
config = {"provider": "OpenAI", "endpoint": str(model.openai_api_base), "model": model.model_name,
    "temperature": model.temperature, "recursion_limit": 40, "max_output_tokens": model.max_tokens,
    "sdk_max_retries": model.root_client.max_retries, "sdk_timeout_seconds": model.root_client.timeout,
    "profile_override": False, "deepagents": version("deepagents"), "python": platform.python_version(),
    "platform": platform.system(), "key_recorded": False}
for base in (Path("results"), Path("report/openai-attempts")):
    for p in base.rglob("run.json"):
        p.with_name("configuration.json").write_text(json.dumps(config, indent=2)+"\n", encoding="utf-8")
Path("report/acceptance/openai-configuration.json").write_text(json.dumps(config, indent=2)+"\n", encoding="utf-8")
print(json.dumps(config), flush=True)
