"""Optional bounded result cache for explicitly versioned, read-only workflows."""
import asyncio
from collections import OrderedDict
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import time


class CachingSystem:
    def __init__(self, system, *, namespace, max_entries=32, ttl_seconds=60, clock=time.monotonic):
        if not isinstance(namespace, str) or not namespace.strip():
            raise ValueError("Provide a data/model/config version namespace")
        if isinstance(max_entries, bool) or not isinstance(max_entries, int) or max_entries < 1:
            raise ValueError("max_entries must be positive")
        if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, (int, float)) or not math.isfinite(ttl_seconds) or ttl_seconds <= 0:
            raise ValueError("TTL must be finite and positive")
        self.system, self.namespace = system, namespace
        self.max_entries, self.ttl_seconds, self.clock = max_entries, ttl_seconds, clock
        self._cache = OrderedDict()
        self._inflight = {}
        self._waiters = {}
        self._usage_claimed = set()
        self._generation = 0
        self.hits = self.misses = self.coalesced = 0
        self.live = system.live

    def _key(self, request):
        payload = json.dumps({"namespace": self.namespace, "generation": self._generation, "request": request}, sort_keys=True,
                             ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    def clear(self):
        """Invalidate stored results; already running requests are not cancelled."""
        self._cache.clear()
        self._generation += 1

    def _valid(self, result):
        chart = result.get("code", {}).get("chart")
        return not chart or Path(chart).is_file()

    async def process(self, request):
        start = self.clock()
        generation = self._generation
        key = self._key(request)
        cached = self._cache.get(key)
        if cached and cached[0] > start and self._valid(cached[1]):
            self.hits += 1
            self._cache.move_to_end(key)
            result = deepcopy(cached[1])
            result.update(cache_hit=True, cache_origin_run_id=result["run_id"],
                          cache_origin_tokens=result["token_usage"], token_usage=0, token_source="none",
                          seconds=self.clock() - start, worker_seconds={})
            return result
        self._cache.pop(key, None)
        joined = key in self._inflight
        if joined:
            self.coalesced += 1
        else:
            self.misses += 1
            self._inflight[key] = asyncio.create_task(self.system.process(deepcopy(request)))
        task = self._inflight[key]
        self._waiters[key] = self._waiters.get(key, 0) + 1
        try:
            result = await asyncio.shield(task)
            if result["status"] == "success" and generation == self._generation:
                self._cache[key] = (self.clock() + self.ttl_seconds, deepcopy(result))
                self._cache.move_to_end(key)
                while len(self._cache) > self.max_entries:
                    self._cache.popitem(last=False)
            response = deepcopy(result)
            response.update(cache_hit=False, coalesced=joined)
            claimed = key in self._usage_claimed
            self._usage_claimed.add(key)
            if claimed:
                response.update(cache_origin_run_id=result["run_id"], cache_origin_tokens=result["token_usage"],
                                token_usage=0, token_source="none", worker_seconds={})
            return response
        finally:
            self._waiters[key] -= 1
            if not self._waiters[key]:
                self._waiters.pop(key)
                self._inflight.pop(key, None)
                self._usage_claimed.discard(key)
                if not task.done():
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
