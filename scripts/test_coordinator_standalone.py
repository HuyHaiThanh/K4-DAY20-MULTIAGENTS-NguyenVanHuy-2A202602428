"""Offline executable demonstration; all outputs are explicitly mocked."""
import asyncio
import logging
from lab.coordinator import Coordinator


class MockWorker:
    def __init__(self, name, delay=0):
        self.name, self.delay = name, delay

    async def process_async(self, content):
        await asyncio.sleep(self.delay)
        return {"mock": True, "worker": self.name, "content": content}


async def main():
    coordinator = Coordinator(worker_agents=[MockWorker("data_agent"), MockWorker("code_agent")])
    simple = await coordinator.process_async("Analyze sales data")
    assert simple["status"] == "success" and len(simple["results"]) == 1
    print("1. Simple task: PASS (mock output)")
    complex_result = await coordinator.process_async("Analyze data and create report")
    assert complex_result["status"] == "success" and len(complex_result["results"]) == 2
    print("2. Multiple workers: PASS (mock outputs)")
    slow = Coordinator(worker_agents=[MockWorker("data_agent", delay=1)])
    timeout = await slow.process_async("Analyze data", timeout=0.02)
    assert timeout["status"] == "error" and timeout["results"][0]["status"] == "timeout"
    assert not slow.active_tasks
    print("3. Timeout and cancellation: PASS")
    print("All standalone coordinator scenarios passed (3/3); no API calls.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
