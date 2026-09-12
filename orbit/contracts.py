"""
orbit.contracts
===============

The SHARED SEAM between the three layers. This is the one file every
developer depends on, so treat it as a contract:

    * Do NOT change a signature or field here without telling the other two.
    * Add new optional fields rather than renaming/removing existing ones.
    * Anything that touches this file goes through a review, never a silent push.

Ownership map (see docs/ARCHITECTURE.md):
    Dev 1 (Browser)  -> implements `BrowserController`
    Dev 2 (Agent)    -> consumes everything here, owns the loop
    Dev 3 (Product)  -> implements `HumanGateway` and `ActivitySink`

Because everyone codes against these Protocols, each developer can build and
test in isolation using the mock/console defaults shipped in the repo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


# --------------------------------------------------------------------------- #
# Action contract (Section 6 of the spec)
# --------------------------------------------------------------------------- #
class ActionType(str, Enum):
    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    SELECT = "select"
    SCROLL = "scroll"
    BACK = "back"
    ASK_USER = "ask_user"
    FINISH = "finish"


class RiskLevel(str, Enum):
    """Set by the agent; used by the control layer to decide on approval."""
    SAFE = "safe"                 # navigation, reading, typing into a draft
    CONSEQUENTIAL = "consequential"  # submit, purchase, delete, send


@dataclass
class AgentAction:
    """One step the agent wants to take.

    `target` MUST be semantic (role / visible text / meaning or a stable
    element reference) — never a hard-coded CSS selector. See spec Section 6.
    """
    type: ActionType
    target: str | None = None       # e.g. "the 'Submit order' button"
    value: str | None = None        # text to type / option to select
    reason: str = ""                # why the agent chose this (for the log)
    risk: RiskLevel = RiskLevel.SAFE


@dataclass
class Observation:
    """A snapshot of the live page the agent reasons over."""
    url: str = ""
    title: str = ""
    page_summary: str = ""          # human/LLM-readable description of state
    interactive_elements: list[str] = field(default_factory=list)
    screenshot_path: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)  # escape hatch


@dataclass
class ActionResult:
    """What happened after an action executed."""
    success: bool
    message: str = ""
    observation: Observation | None = None
    error: str | None = None


@dataclass
class ClarificationRequest:
    """Agent -> human when intent/target is ambiguous (spec: 'which John?')."""
    question: str
    options: list[str] = field(default_factory=list)


@dataclass
class ApprovalRequest:
    """Agent -> human before a consequential action executes."""
    action: AgentAction
    summary: str = ""


# --------------------------------------------------------------------------- #
# Layer interfaces — implement these in your own package.
# --------------------------------------------------------------------------- #
@runtime_checkable
class BrowserController(Protocol):
    """DEV 1 owns this. Wraps the Browser Use runtime + Chrome/Playwright.

    Keep it dumb: this layer executes actions and reports what it sees. It does
    NOT decide what to do next (that's the agent) and does NOT talk to the user.
    """

    async def start(self) -> None: ...
    async def stop(self) -> None: ...

    async def observe(self) -> Observation:
        """Return the current page state."""
        ...

    async def execute(self, action: AgentAction) -> ActionResult:
        """Perform one AgentAction and return the result + new observation."""
        ...


@runtime_checkable
class HumanGateway(Protocol):
    """DEV 3 owns this. The human-in-the-loop channel.

    The agent calls these when it needs the person. In the demo UI these render
    as a prompt / an Approve|Reject button; the console default just uses stdin.
    """

    async def ask(self, request: ClarificationRequest) -> str:
        """Return the human's answer to a clarification question."""
        ...

    async def approve(self, request: ApprovalRequest) -> bool:
        """Return True to allow a consequential action, False to skip it."""
        ...


@runtime_checkable
class ActivitySink(Protocol):
    """DEV 3 owns this. Where the observe->action->result->verify trace goes.

    The agent emits events; the demo UI renders them as the live activity log
    (spec Section 10, step 2). The console default just prints.
    """

    def emit(self, kind: str, payload: dict[str, Any]) -> None: ...
