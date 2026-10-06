import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
from lab.benchmarking import Benchmark
from lab.system import MultiAgentSystem


async def main(args):
    output = Path(args.output)
    system = MultiAgentSystem(output.parent / ("live-runs" if args.live else "offline-runs"), live=args.live)
    bench = Benchmark()
    for name, request in [("Simple data query", "Analyze supplied sales data"),
                          ("Code generation", "Create a chart"),
                          ("Complex workflow", "Analyze sales data and create chart")]:
        record = await bench.run_test(name, request, system, iterations=args.iterations, pace_seconds=args.pace_seconds)
        print(f"{name}: {record['successes']}/{record['iterations']} success, median={record['median']:.3f}s p99={record['p99']:.3f}s", flush=True)
    report = {"timestamp": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
              "python": platform.python_version(), "mode": "live" if args.live else "offline-scripted",
              "fixture": "supplied local sales: Jan=10, Feb=20; ratings=85/90/80/85",
              "limits": "P99 from 3 samples is descriptive, not a population estimate; offline tokens are synthetic; failed request usage may be incomplete",
              "results": bench.results}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Opt-in: consume model API quota using .env")
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--output", default="report/acceptance/benchmark-offline.json")
    parser.add_argument("--pace-seconds", type=float, default=0, help="Delay before each sample; included in throughput window, excluded from request latency")
    asyncio.run(main(parser.parse_args()))
