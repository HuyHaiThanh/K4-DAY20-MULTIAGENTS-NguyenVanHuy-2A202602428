"""Sequential official runs with preserved attempts and bounded infrastructure retries.

No task prompts, tool schemas, skills or grading are changed. Run in WSL.
"""
import argparse
import json
import shutil
import time
from pathlib import Path

from lab.model import make_model
from lab.runner import run_task
from langchain_core.callbacks import BaseCallbackHandler


class Progress(BaseCallbackHandler):
    def on_llm_end(self, response, **kwargs):
        usage = getattr(response.generations[0][0].message, "usage_metadata", None)
        print("model response received usage=" + json.dumps(usage), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("condition", choices=["baseline", "subagents", "skills-auto"])
    ap.add_argument("tasks", nargs="+")
    ap.add_argument("--results", default="results")
    ap.add_argument("--model", default=None, help="Explicit model ID at the same configured endpoint")
    ap.add_argument("--profile-input-limit", type=int, default=11000)
    ap.add_argument("--max-output-tokens", type=int, default=4096)
    args = ap.parse_args()
    if args.max_output_tokens < 1 or int(args.profile_input_limit * .95) <= args.max_output_tokens:
        ap.error("profile input limit must leave a positive budget after output reservation")
    model = make_model()
    if args.model:
        model.model_name = args.model
    # Keep make_model's SDK client defaults. Assigning the LangChain fields
    # after construction does NOT rebuild the already-created SDK clients.
    model.max_tokens = args.max_output_tokens
    # The gateway rejects a SINGLE request above 7k input tokens. Expose an
    # Deep Agents reserves output + 5%: 11000 * .95 - 4096 = 6354 input
    # tokens, leaving margin below the gateway's 7000 input limit.
    # Apply to every condition; this does not alter task/agent prompts.
    model.profile = {**(model.profile or {}), "max_input_tokens": args.profile_input_limit}
    model.callbacks = [Progress()]
    config = {"model": model.model_name, "temperature": model.temperature, "max_tokens": args.max_output_tokens,
              "max_retries": model.root_client.max_retries,
              "timeout_seconds": model.root_client.timeout, "recursion_limit": 40,
              "profile_max_input_tokens": args.profile_input_limit,
              "effective_input_budget": int(args.profile_input_limit * .95) - args.max_output_tokens}
    for task in args.tasks:
        target = Path(args.results) / args.condition / task
        for attempt in range(1, 4):
            if (target / "run.json").exists():
                previous = json.loads((target / "run.json").read_text())
                if not previous.get("error"):
                    saved_config = target / "configuration.json"
                    if not saved_config.exists() or json.loads(saved_config.read_text()) != config:
                        raise RuntimeError(f"Existing valid run uses a different/unknown configuration: {target}; archive it before changing configuration")
                    print(f"SKIP existing successful {args.condition}/{task}", flush=True)
                    break
                archive = Path("report/official-attempts") / args.condition / task / str(time.time_ns())
                archive.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(target, archive)
            record = run_task(task, args.condition, args.results, model=model, recursion_limit=40)
            (target / "configuration.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
            print(json.dumps({k: record[k] for k in ("condition", "task", "passed", "total", "tokens", "seconds", "tool_calls", "subagent_calls", "skills_read")}) + f" error={bool(record['error'])}", flush=True)
            if not record["error"]:
                break
            if "429" in record["error"] or "rate_limit" in record["error"]:
                raise RuntimeError(f"Quota/rate limit: {args.condition}/{task}; preserve run and wait for provider reset")
            if "ContextOverflowError" in record["error"]:
                raise RuntimeError(f"Context budget cannot fit: {args.condition}/{task}; fix configuration before retry")
            if attempt == 3:
                raise RuntimeError(f"Infrastructure/model failure after 3 attempts: {args.condition}/{task}; see run.json")
            time.sleep(60)
        time.sleep(15)


if __name__ == "__main__":
    main()
