"""Bonus 6c: compare identical read-only fixture requests, offline only."""
import asyncio
import json
from pathlib import Path
import time
from lab.system import MultiAgentSystem
from lab.caching import CachingSystem


async def main():
    root = Path("report/bonus-cache")
    system = MultiAgentSystem(root / "runs")
    cache = CachingSystem(system, namespace="sales-fixture-v1/scripted-model-v1/config-v1", ttl_seconds=60)
    request = "Analyze sales data and create chart"
    measurements = {}
    for label, target in (("uncached", system), ("cached", cache)):
        samples = []
        for _ in range(5):
            start = time.monotonic(); result = await target.process(request)
            assert result["status"] == "success"
            samples.append({"seconds": time.monotonic()-start, "cache_hit": result.get("cache_hit", False),
                            "run_id": result["run_id"], "synthetic_tokens_this_call": result["token_usage"]})
        measurements[label] = {"samples": samples, "wall_seconds": sum(s["seconds"] for s in samples),
                               "requests_per_minute": 5/sum(s["seconds"] for s in samples)*60,
                               "underlying_run_ids": sorted(set(s["run_id"] for s in samples))}
    root.mkdir(parents=True, exist_ok=True)
    report = {"mode": "offline-scripted", "request": request, "iterations": 5, "measurements": measurements,
              "cache": {"hits": cache.hits, "misses": cache.misses, "ttl_seconds": 60, "max_entries": 32},
              "limits": "Identical warm fixture requests only; not evidence of production/API throughput; no provider tokens spent"}
    (root / "benchmark.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps({"cache":report["cache"],"requests_per_minute":{key:value["requests_per_minute"] for key,value in measurements.items()}},indent=2))


if __name__ == "__main__": asyncio.run(main())
