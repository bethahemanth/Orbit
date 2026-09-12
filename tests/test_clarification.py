"""Tests for clarification and approval flows through the agent loop."""

import asyncio
from unittest.mock import MagicMock

from orbit.agent.loop import OrbitAgent
from orbit.contracts import (
    ActionType,
    AgentAction,
    Observation,
    RiskLevel,
)


# ------------------------------------------------------------------ #
# Helpers — deterministic planners for testing.
# ------------------------------------------------------------------ #
class ScriptedPlanner:
    """Returns a pre-scripted sequence of actions, one per call."""

    def __init__(self, actions: list[AgentAction]) -> None:
        self._actions = list(actions)
        self._index = 0

    async def next_action(self, goal: str, obs: Observation) -> AgentAction:
        action = self._actions[self._index]
        self._index = min(self._index + 1, len(self._actions) - 1)
        return action


class RecordingGateway:
    """Records calls to ask() and approve(); returns canned answers."""

    def __init__(self, ask_answer: str = "Smith", approve_answer: bool = True):
        self.ask_calls: list[str] = []
        self.approve_calls: list[str] = []
        self.ask_answer = ask_answer
        self.approve_answer = approve_answer

    async def ask(self, request):
        self.ask_calls.append(request.question)
        return self.ask_answer

    async def approve(self, request):
        self.approve_calls.append(request.summary)
        return self.approve_answer


class RecordingSink:
    """Records all emitted events."""

    def __init__(self):
        self.events: list[tuple[str, dict]] = []

    def emit(self, kind: str, payload: dict) -> None:
        self.events.append((kind, payload))

    def kinds(self) -> list[str]:
        return [k for k, _ in self.events]


def _mock_browser(url="http://127.0.0.1:5000", summary="Orders page"):
    """Create a mock browser that returns consistent observations."""
    obs = Observation(
        url=url,
        title="Portal",
        page_summary=summary,
        interactive_elements=["'Process' button"],
    )
    browser = MagicMock()
    browser.start = _async_noop
    browser.stop = _async_noop
    browser.observe = _async_return(obs)
    # execute returns success with the same observation (page didn't change)
    from orbit.contracts import ActionResult
    browser.execute = _async_return(
        ActionResult(success=True, message="ok", observation=obs)
    )
    return browser


async def _async_noop(*_a, **_k):
    pass


def _async_return(val):
    async def _fn(*_a, **_k):
        return val
    return _fn


# ------------------------------------------------------------------ #
# Clarification flow
# ------------------------------------------------------------------ #
def test_clarification_asks_user_and_augments_goal():
    """ASK_USER action triggers gateway.ask() and appends the answer."""
    planner = ScriptedPlanner([
        AgentAction(type=ActionType.ASK_USER, value="Which John? Smith, Carter, or Diaz?"),
        AgentAction(type=ActionType.FINISH, reason="done"),
    ])
    gateway = RecordingGateway(ask_answer="Smith")
    sink = RecordingSink()

    agent = OrbitAgent(_mock_browser(), gateway, sink, max_steps=10, planner=planner)
    outcome = asyncio.run(agent.run("Process John's order"))

    assert outcome == "done"
    assert len(gateway.ask_calls) == 1
    assert "Which John?" in gateway.ask_calls[0]
    assert "clarify" in sink.kinds()


# ------------------------------------------------------------------ #
# Approval flow — approved
# ------------------------------------------------------------------ #
def test_approval_granted_executes_action():
    planner = ScriptedPlanner([
        AgentAction(type=ActionType.CLICK, target="Submit Order",
                    risk=RiskLevel.CONSEQUENTIAL, reason="submit the order"),
        AgentAction(type=ActionType.FINISH, reason="done"),
    ])
    gateway = RecordingGateway(approve_answer=True)
    sink = RecordingSink()

    agent = OrbitAgent(_mock_browser(), gateway, sink, max_steps=10, planner=planner)
    outcome = asyncio.run(agent.run("Submit the order"))

    assert outcome == "done"
    assert len(gateway.approve_calls) == 1
    assert "approval" in sink.kinds()
    # Action was executed (we should see an "act" event)
    assert "act" in sink.kinds()


# ------------------------------------------------------------------ #
# Approval flow — denied
# ------------------------------------------------------------------ #
def test_approval_denied_skips_action():
    planner = ScriptedPlanner([
        AgentAction(type=ActionType.CLICK, target="Delete All",
                    risk=RiskLevel.CONSEQUENTIAL, reason="delete everything"),
        AgentAction(type=ActionType.FINISH, reason="done"),
    ])
    gateway = RecordingGateway(approve_answer=False)
    sink = RecordingSink()

    agent = OrbitAgent(_mock_browser(), gateway, sink, max_steps=10, planner=planner)
    outcome = asyncio.run(agent.run("Delete all records"))

    assert outcome == "done"
    assert len(gateway.approve_calls) == 1
    # Action was NOT executed — no "act" event between approval and the finish
    approval_idx = sink.kinds().index("approval")
    events_after_approval = sink.kinds()[approval_idx + 1:]
    assert "act" not in events_after_approval or events_after_approval[0] != "act"


# ------------------------------------------------------------------ #
# Mixed flow: ask -> consequential click -> finish
# ------------------------------------------------------------------ #
def test_mixed_clarify_then_approve_then_finish():
    planner = ScriptedPlanner([
        AgentAction(type=ActionType.ASK_USER, value="Which account?"),
        AgentAction(type=ActionType.CLICK, target="Confirm Purchase",
                    risk=RiskLevel.CONSEQUENTIAL, reason="buy it"),
        AgentAction(type=ActionType.FINISH, reason="all done"),
    ])
    gateway = RecordingGateway(ask_answer="Account A", approve_answer=True)
    sink = RecordingSink()

    agent = OrbitAgent(_mock_browser(), gateway, sink, max_steps=10, planner=planner)
    outcome = asyncio.run(agent.run("Buy the item"))

    assert outcome == "done"
    assert len(gateway.ask_calls) == 1
    assert len(gateway.approve_calls) == 1

    kinds = sink.kinds()
    assert "clarify" in kinds
    assert "approval" in kinds
    assert "complete" in kinds
