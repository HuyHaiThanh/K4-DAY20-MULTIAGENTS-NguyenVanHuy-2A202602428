import argparse
import asyncio
import json
import logging
from pathlib import Path
from lab.system import MultiAgentSystem


async def main(args):
    root = Path("report/acceptance")
    root.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, filename=root / "debug.log", encoding="utf-8",
                        format="%(asctime)s %(name)s %(levelname)s %(message)s", force=True)
    logs = root / "logs"
    logs.mkdir(exist_ok=True)
    for name in ("coordinator", "data_agent", "code_agent", "evaluator_agent", "tools"):
        handler = logging.FileHandler(logs / f"{name}.log", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
        logging.getLogger(f"lab.{name}").addHandler(handler)
    result = await MultiAgentSystem(root / "debug-runs", live=args.live).process(args.task)
    (root / "debug-last.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (logs / "communication.jsonl").write_text("".join(json.dumps(message) + "\n" for message in result["messages"]), encoding="utf-8")
    print(json.dumps({"status": result["status"], "error": result["error"], "seconds": result["seconds"], "run_id": result["run_id"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", default="Analyze sales and create chart")
    parser.add_argument("--live", action="store_true")
    asyncio.run(main(parser.parse_args()))
