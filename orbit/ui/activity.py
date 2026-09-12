"""
orbit.ui.activity   ---  DEV 3 (Product/Demo) owns this file.
============================================================

The live activity log + approval UI shown during the demo (spec Section 10,
step 2). It is an ActivitySink + HumanGateway, so it drops straight into the
agent in place of the console defaults.

WebActivitySink: bounded deque history, per-subscriber queues, thread-safe.
WebGateway: pending record with UUID correlation, thread-safe answer handoff.
"""

from __future__ import annotations

import asyncio
import queue
import threading
import uuid
from collections import deque
from dataclasses import asdict
from typing import Any

from orbit.contracts import (
    ActivitySink,
    ApprovalRequest,
    ClarificationRequest,
    HumanGateway,
)


class WebActivitySink(ActivitySink):
    """Push activity events to the browser via SSE.

    Thread-safe: emit() is called from the agent's asyncio thread while
    subscribe/unsubscribe are called from Flask request threads.
    """

    def __init__(self, max_history: int = 500) -> None:
        self.history: deque[dict[str, Any]] = deque(maxlen=max_history)
        self.subscribers: set[queue.Queue[dict[str, Any]]] = set()
        self.lock = threading.Lock()
        self.max_history = max_history

    def emit(self, kind: str, payload: dict[str, Any]) -> None:
        """Record event and push to all active subscribers."""
        event = {"kind": kind, **payload}
        with self.lock:
            self.history.append(event)
            for q in self.subscribers:
                try:
                    q.put_nowait(event)
                except queue.Full:
                    # Drop oldest if subscriber queue is full (bounded)
                    try:
                        q.get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        q.put_nowait(event)
                    except queue.Full:
                        pass

    def subscribe(self) -> queue.Queue[dict[str, Any]]:
        """Create and register a new subscriber queue for SSE streaming."""
        q: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=200)
        with self.lock:
            self.subscribers.add(q)
        return q

    def unsubscribe(self, q: queue.Queue[dict[str, Any]]) -> None:
        """Remove a subscriber queue."""
        with self.lock:
            self.subscribers.discard(q)

    def recent(self) -> list[dict[str, Any]]:
        """Return a snapshot of recent history."""
        with self.lock:
            return list(self.history)


class WebGateway(HumanGateway):
    """Web-based human-in-the-loop channel.

    Bridges the async agent loop to synchronous Flask request threads using
    thread-safe primitives. Only one pending interaction at a time.
    """

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self._pending: dict[str, Any] | None = None

    async def ask(self, request: ClarificationRequest) -> str:
        """Surface a clarification question in the UI and block until answered."""
        interaction_id = str(uuid.uuid4())
        answer_queue: queue.Queue[str] = queue.Queue(maxsize=1)

        public = {
            "id": interaction_id,
            "kind": "clarification",
            "question": request.question,
            "options": list(request.options) if request.options else [],
        }

        with self.lock:
            if self._pending is not None:
                raise RuntimeError("Another interaction is already pending")
            self._pending = {
                "id": interaction_id,
                "kind": "clarification",
                "public": public,
                "answer_queue": answer_queue,
            }

        try:
            # Block until Flask thread delivers the answer
            answer = await asyncio.to_thread(answer_queue.get)
            return answer
        finally:
            with self.lock:
                if self._pending and self._pending["id"] == interaction_id:
                    self._pending = None

    async def approve(self, request: ApprovalRequest) -> bool:
        """Show Approve/Reject in the UI and block until the user decides."""
        interaction_id = str(uuid.uuid4())
        answer_queue: queue.Queue[bool] = queue.Queue(maxsize=1)

        # Build a JSON-safe action projection
        action = request.action
        action_projection = {
            "type": action.type.value,
            "target": action.target,
            "value": action.value,
            "risk": action.risk.value,
        }

        public = {
            "id": interaction_id,
            "kind": "approval",
            "summary": request.summary or "Consequential action pending",
            "action": action_projection,
        }

        with self.lock:
            if self._pending is not None:
                raise RuntimeError("Another interaction is already pending")
            self._pending = {
                "id": interaction_id,
                "kind": "approval",
                "public": public,
                "answer_queue": answer_queue,
            }

        try:
            approved = await asyncio.to_thread(answer_queue.get)
            return approved
        finally:
            with self.lock:
                if self._pending and self._pending["id"] == interaction_id:
                    self._pending = None

    def get_pending(self) -> dict[str, Any] | None:
        """Return the JSON-safe public fields of the current pending request."""
        with self.lock:
            if self._pending is None:
                return None
            return dict(self._pending["public"])

    def resolve(self, interaction_id: str, answer: Any) -> bool:
        """Resolve a pending interaction by ID. Returns True if resolved."""
        with self.lock:
            if self._pending is None:
                return False
            if self._pending["id"] != interaction_id:
                return False

            pending = self._pending
            kind = pending["kind"]
            answer_queue = pending["answer_queue"]

        # Enqueue the answer (outside lock to avoid deadlock)
        if kind == "clarification":
            answer_queue.put(str(answer))
        elif kind == "approval":
            answer_queue.put(bool(answer))
        else:
            return False

        return True
