"""Bounded, in-memory async mailboxes with correlated response delivery."""
import asyncio
from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
import math
from uuid import uuid4
import json


class MessageQueue:
    def __init__(self, capacity=128, history_limit=1000):
        if any(isinstance(v, bool) or not isinstance(v, int) or v < 1 for v in (capacity, history_limit)):
            raise ValueError("Queue limits must be positive integers")
        self.capacity = capacity
        self.queues = {}
        self._conditions = {}
        self.message_log = deque(maxlen=history_limit)

    def register_agent(self, agent_name):
        if not isinstance(agent_name, str) or not agent_name.strip():
            raise ValueError("Agent name is required")
        if agent_name not in self.queues:
            self.queues[agent_name] = deque()
            self._conditions[agent_name] = asyncio.Condition()

    async def send_message(self, from_agent, to_agent, message):
        if from_agent not in self.queues or to_agent not in self.queues:
            raise ValueError("Sender and recipient must be registered")
        if not isinstance(message, dict):
            raise ValueError("Message must be a dict")
        encoded = json.dumps(message, allow_nan=False)
        if len(encoded.encode("utf-8")) > 1_000_000:
            raise ValueError("Message size limit exceeded")
        envelope = deepcopy(message)
        envelope.update({"from": from_agent, "to": to_agent,
                         "timestamp": datetime.now(timezone.utc).isoformat(), "id": uuid4().hex})
        async with self._conditions[to_agent]:
            if len(self.queues[to_agent]) >= self.capacity:
                raise ValueError("Mailbox capacity exceeded")
            self.queues[to_agent].append(envelope)
            self.message_log.append(deepcopy(envelope))
            self._conditions[to_agent].notify_all()
        return envelope["id"]

    async def receive_message(self, agent_name, timeout=30, *, correlation_id=None):
        if agent_name not in self.queues:
            raise ValueError("Agent is not registered")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Timeout must be finite and positive")
        async def receive():
            async with self._conditions[agent_name]:
                while True:
                    for message in self.queues[agent_name]:
                        if correlation_id is None or message.get("correlation_id") == correlation_id:
                            self.queues[agent_name].remove(message)
                            return deepcopy(message)
                    await self._conditions[agent_name].wait()
        try:
            async with asyncio.timeout(timeout):
                return await receive()
        except TimeoutError:
            raise TimeoutError(f"No matching message for {agent_name}") from None

    def discard(self, correlation_id):
        """Remove pending envelopes for an exchange after cancellation/completion."""
        for name, inbox in self.queues.items():
            self.queues[name] = deque(m for m in inbox if m.get("correlation_id") != correlation_id)

    def get_message_log(self, agent_name=None):
        return deepcopy([m for m in self.message_log if agent_name is None or agent_name in (m["from"], m["to"])])

    async def exchange(self, sender, worker, content, timeout):
        """Dispatch a worker via a correlated request/result pair; no daemon tasks."""
        self.register_agent(sender)
        self.register_agent(worker.name)
        correlation = uuid4().hex
        async def serve():
            request = await self.receive_message(worker.name, timeout, correlation_id=correlation)
            result = await worker.process_async(request["content"])
            await self.send_message(worker.name, sender, {"type": "result", "correlation_id": correlation, "content": result})
        handler = None
        try:
            await self.send_message(sender, worker.name, {"type": "task", "correlation_id": correlation, "content": content})
            handler = asyncio.create_task(serve())
            # Await the handler too: exceptions must propagate instead of becoming a timeout.
            async with asyncio.timeout(timeout):
                await handler
                reply = await self.receive_message(sender, timeout, correlation_id=correlation)
            return reply["content"]
        finally:
            if handler is not None:
                handler.cancel()
                await asyncio.gather(handler, return_exceptions=True)
            self.discard(correlation)
