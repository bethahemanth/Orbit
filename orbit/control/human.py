"""
orbit.control.human
===================

Console defaults for the human-in-the-loop channel and the activity trace.

DEV 3 replaces these with the real demo UI (a web prompt + Approve/Reject
button, and the live activity log). Everyone else can run against these console
versions today. Both implement the Protocols in orbit.contracts.
"""

from __future__ import annotations

from typing import Any

from orbit.contracts import (
    ActivitySink,
    ApprovalRequest,
    ClarificationRequest,
    HumanGateway,
)


class ConsoleGateway(HumanGateway):
    """Asks the user via stdin. Dev 3: mirror this behaviour in the web UI."""

    async def ask(self, request: ClarificationRequest) -> str:
        print(f"\n[CLARIFY] {request.question}")
        if request.options:
            for i, opt in enumerate(request.options, 1):
                print(f"   {i}. {opt}")
        return input("Your answer: ").strip()

    async def approve(self, request: ApprovalRequest) -> bool:
        print(f"\n[APPROVAL NEEDED] {request.summary}")
        print(f"   action: {request.action.type.value} -> {request.action.target}")
        return input("Approve? [y/N]: ").strip().lower() == "y"


class ConsoleActivitySink(ActivitySink):
    """Prints the observe->action->result->verify trace. Dev 3: render this."""

    def emit(self, kind: str, payload: dict[str, Any]) -> None:
        print(f"[{kind.upper()}] {payload}")
