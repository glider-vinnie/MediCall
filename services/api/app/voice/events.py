from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any


class VoiceEventHub:
    """Small in-process event fan-out for a single API instance.

    Events are deliberately session-scoped and never persisted. This keeps live
    transcripts out of the dashboard database and avoids logging personal data.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)

    async def publish(self, session_id: str, event_type: str, **payload: Any) -> None:
        event = {"type": event_type, **payload}
        for queue in tuple(self._subscribers[session_id]):
            if queue.full():
                continue
            queue.put_nowait(event)

    def subscribe(self, session_id: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        self._subscribers[session_id].add(queue)
        return queue

    def unsubscribe(self, session_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        subscribers = self._subscribers.get(session_id)
        if not subscribers:
            return
        subscribers.discard(queue)
        if not subscribers:
            self._subscribers.pop(session_id, None)
