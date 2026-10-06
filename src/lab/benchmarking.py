"""Measured benchmark statistics; live and synthetic usage are kept separate."""
import asyncio
import math
import statistics
import time


def percentile(values, quantile):
    if not values or not 0 <= quantile <= 1:
        raise ValueError("Need samples and a quantile between zero and one")
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower, upper = math.floor(position), math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


class Benchmark:
    def __init__(self):
        self.results = []

    async def run_test(self, name, request, system, iterations=3, concurrency=1, pace_seconds=0):
        if any(isinstance(v, bool) or not isinstance(v, int) or v < 1 for v in (iterations, concurrency)):
            raise ValueError("Iterations/concurrency must be positive integers")
        if isinstance(pace_seconds, bool) or not isinstance(pace_seconds, (int, float)) or not math.isfinite(pace_seconds) or pace_seconds < 0:
            raise ValueError("Pacing must be finite and nonnegative")
        gate = asyncio.Semaphore(concurrency)
        async def sample():
            async with gate:
                if pace_seconds:
                    await asyncio.sleep(pace_seconds)
                start = time.monotonic()
                result = await system.process(request)
                return {"latency": time.monotonic() - start, "run_id": result["run_id"],
                        "status": result["status"], "error": result.get("error"),
                        "tokens": result["token_usage"], "token_source": result["token_source"],
                        "tokens_complete": result["tokens_complete"],
                        "worker_seconds": result["worker_seconds"]}
        start = time.monotonic()
        samples = await asyncio.gather(*(sample() for _ in range(iterations)))
        elapsed = time.monotonic() - start
        latency = [sample["latency"] for sample in samples]
        successes = sum(sample["status"] == "success" for sample in samples)
        worker_seconds = {}
        for entry in samples:
            for worker, duration in entry["worker_seconds"].items():
                worker_seconds[worker] = worker_seconds.get(worker, 0) + duration
        record = {"name": name, "mode": "live" if system.live else "offline-scripted", "iterations": iterations,
                  "concurrency": concurrency, "min": min(latency), "max": max(latency), "avg": statistics.mean(latency),
                  "pace_seconds": pace_seconds,
                  "median": statistics.median(latency), "p50": percentile(latency, .5), "p99": percentile(latency, .99),
                  "elapsed": elapsed, "throughput_requests_per_minute": iterations / elapsed * 60,
                  "successful_requests_per_minute": successes / elapsed * 60,
                  "successes": successes, "error_rate": 1 - successes / iterations,
                  "worker_busy_seconds": worker_seconds,
                  "worker_busy_fraction_per_configured_slot": {worker: duration / (elapsed * concurrency) for worker, duration in worker_seconds.items()},
                  "provider_tokens": sum(s["tokens"] for s in samples if s["token_source"] == "provider"),
                  "token_usage_complete": all(s["tokens_complete"] for s in samples),
                  "synthetic_tokens": sum(s["tokens"] for s in samples if s["token_source"] == "synthetic"),
                  "samples": samples}
        self.results.append(record)
        return record
