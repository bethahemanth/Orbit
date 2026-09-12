"""
orbit.ui.activity   ---  DEV 3 (Product/Demo) owns this file.
============================================================

The live activity log + approval UI shown during the demo (spec Section 10,
step 2). It is an ActivitySink + HumanGateway, so it drops straight into the
agent in place of the console defaults.

TODO(dev3):
  * Render observe -> action -> result -> verify as a live feed (SSE/websocket
    or simple polling is fine for a hackathon).
  * Render clarification questions and an Approve|Reject button for
    consequential actions, and feed the human's answer back to the agent.
This stub keeps the interface real so Dev 2 can wire it in early.
"""

from __future__ import annotations

from typing import Any

from orbit.contracts import ActivitySink, ApprovalRequest, ClarificationRequest, HumanGateway


class WebActivitySink(ActivitySink):
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def emit(self, kind: str, payload: dict[str, Any]) -> None:
        self.events.append({"kind": kind, **payload})
        # TODO(dev3): push to the browser (SSE/websocket) so the panel updates live.


class WebGateway(HumanGateway):
    async def ask(self, request: ClarificationRequest) -> str:
        raise NotImplementedError("dev3: surface the question in the UI, return the answer")

    async def approve(self, request: ApprovalRequest) -> bool:
        raise NotImplementedError("dev3: show Approve|Reject, return the choice")
