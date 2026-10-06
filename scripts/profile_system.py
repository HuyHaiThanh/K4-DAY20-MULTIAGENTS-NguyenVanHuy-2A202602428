import asyncio
import cProfile
from pathlib import Path
import pstats
from lab.system import MultiAgentSystem


async def run():
    system = MultiAgentSystem("report/acceptance/profile-runs")
    for _ in range(5):
        result = await system.process("Analyze data and create chart")
        assert result["status"] == "success", result["error"]


if __name__ == "__main__":
    root = Path("report/acceptance")
    root.mkdir(parents=True, exist_ok=True)
    profiler = cProfile.Profile()
    profiler.enable()
    asyncio.run(run())
    profiler.disable()
    profiler.dump_stats(str(root / "profile.pstats"))
    with (root / "profile.txt").open("w", encoding="utf-8") as output:
        pstats.Stats(profiler, stream=output).sort_stats("cumulative").print_stats(20)
    profile_text = root / "profile.txt"
    profile_text.write_text(profile_text.read_text(encoding="utf-8").rstrip() + "\n", encoding="utf-8")
    print(f"Saved {profile_text}")
