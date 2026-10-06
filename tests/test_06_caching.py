import asyncio
from copy import deepcopy
import pytest
from lab.caching import CachingSystem


class FakeSystem:
    live = False
    def __init__(self): self.calls = 0; self.fail = False; self.delay = 0
    async def process(self, request):
        self.calls += 1
        await asyncio.sleep(self.delay)
        return {"run_id": str(self.calls), "status": "error" if self.fail else "success",
                "token_usage": 120, "token_source": "synthetic", "worker_seconds": {"worker": .1}, "request": deepcopy(request)}


def test_cache_hit_isolation_and_no_double_count():
    async def run():
        underlying = FakeSystem()
        cache = CachingSystem(underlying, namespace="fixture-v1/model-v1")
        first = await cache.process({"content": "a"})
        first["request"]["content"] = "changed"
        hit = await cache.process({"content": "a"})
        assert hit["cache_hit"] and hit["request"]["content"] == "a"
        assert hit["token_usage"] == 0 and hit["cache_origin_tokens"] == 120
        assert underlying.calls == 1
    asyncio.run(run())


def test_expiry_eviction_and_failure():
    async def run():
        clock = [0.0]
        underlying = FakeSystem()
        cache = CachingSystem(underlying, namespace="v1", max_entries=1, ttl_seconds=1, clock=lambda: clock[0])
        await cache.process("a")
        clock[0] = 2
        await cache.process("a")
        await cache.process("b")
        await cache.process("a")
        assert underlying.calls == 4
        underlying.fail = True
        await cache.process("error")
        await cache.process("error")
        assert underlying.calls == 6
    asyncio.run(run())


def test_singleflight_and_cancellation():
    async def run():
        underlying = FakeSystem(); underlying.delay = .05
        cache = CachingSystem(underlying, namespace="v1")
        tasks = [asyncio.create_task(cache.process("a")) for _ in range(3)]
        await asyncio.sleep(.01)
        tasks[0].cancel()
        with pytest.raises(asyncio.CancelledError): await tasks[0]
        results = await asyncio.gather(*tasks[1:])
        assert all(r["status"] == "success" for r in results) and underlying.calls == 1
        assert sum(r["token_usage"] for r in results) == 120
        assert not cache._inflight
        pending = asyncio.create_task(cache.process("b"))
        await asyncio.sleep(.01)
        pending.cancel()
        with pytest.raises(asyncio.CancelledError): await pending
        assert not cache._inflight
    asyncio.run(run())


def test_clear_does_not_cache_old_inflight_result():
    async def run():
        underlying = FakeSystem(); underlying.delay = .03
        cache = CachingSystem(underlying, namespace="v1")
        pending = asyncio.create_task(cache.process("a"))
        await asyncio.sleep(.01)
        cache.clear()
        await pending
        result = await cache.process("a")
        assert not result["cache_hit"] and underlying.calls == 2
    asyncio.run(run())


def test_deleted_artifact_invalidates(tmp_path):
    async def run():
        class Artifacts(FakeSystem):
            async def process(self, request):
                result = await super().process(request)
                path = tmp_path / "chart.svg"; path.write_text("chart")
                result["code"] = {"chart": str(path)}
                return result
        underlying = Artifacts(); cache = CachingSystem(underlying, namespace="v1")
        await cache.process("a")
        (tmp_path / "chart.svg").unlink()
        result = await cache.process("a")
        assert not result["cache_hit"] and underlying.calls == 2
    asyncio.run(run())
