"""Local Linux resource observations; maxima are not incremental RAM per request."""
import asyncio
import json
from pathlib import Path
import resource
import time
from lab.system import MultiAgentSystem


async def main():
    root = Path("report/acceptance")
    system = MultiAgentSystem(root / "resource-runs")
    measurements = []
    for concurrency in (1, 10):
        before_self = resource.getrusage(resource.RUSAGE_SELF)
        before_child = resource.getrusage(resource.RUSAGE_CHILDREN)
        start = time.monotonic()
        results = await asyncio.gather(*(system.process("Analyze sales data and create chart") for _ in range(concurrency)))
        wall = time.monotonic() - start
        after_self = resource.getrusage(resource.RUSAGE_SELF)
        after_child = resource.getrusage(resource.RUSAGE_CHILDREN)
        measurements.append({"concurrency": concurrency, "mode": "offline-scripted", "wall_seconds": wall,
            "successes": sum(r["status"] == "success" for r in results),
            "parent_cpu_seconds": after_self.ru_utime + after_self.ru_stime - before_self.ru_utime - before_self.ru_stime,
            "children_cpu_seconds": after_child.ru_utime + after_child.ru_stime - before_child.ru_utime - before_child.ru_stime,
            "parent_peak_rss_kib": after_self.ru_maxrss, "children_peak_rss_kib": after_child.ru_maxrss,
            "run_ids": [r["run_id"] for r in results]})
    output = {"platform": "WSL Linux", "scope": "process-lifetime RSS maxima; child RSS is max of reaped children, not sum; no claim of linear memory scaling", "measurements": measurements}
    (root / "resources.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
