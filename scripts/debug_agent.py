"""Debug a selected worker stage using the same evidence-producing pipeline."""
import argparse
import asyncio
import json
from lab.system import MultiAgentSystem


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", choices=["data_agent", "code_agent", "evaluator_agent"], required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    kind = {"data_agent": "data_analysis", "code_agent": "code_generation", "evaluator_agent": "evaluation"}[args.agent]
    result = asyncio.run(MultiAgentSystem("report/acceptance/agent-runs", live=args.live).process({"task_type": kind, "content": args.task}))
    print(json.dumps(result, indent=2, ensure_ascii=True))
