"""Tests for OrbitAgent.verify() and recovery logic."""

import asyncio
from unittest.mock import MagicMock

from orbit.agent.loop import OrbitAgent, _MAX_CONSECUTIVE_FAILURES
from orbit.contracts import (
    ActionType,
    ActionResult,
    AgentAction,
    Observation,
    RiskLevel,
)


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #
def _obs(url="http://127.0.0.1:5000", summary="Orders page", elements=None):
    return Observation(
        url=url,
        title="Portal",
        page_summary=summary,
        interactive_elements=elements or ["'Process' button"],
    )


class ScriptedPlanner:
    def __init__(self, actions):
        self._actions = list(actions)
        self._i = 0

    async def next_action(self, goal, obs):
        a = self._actions[self._i]
        self._i = min(self._i + 1, len(self._actions) - 1)
        return a


class RecordingGateway:
    def __init__(self, ask_answer="try again"):
        self.ask_calls = []
        self.ask_answer = ask_answer

    async def ask(self, req):
        self.ask_calls.append(req.question)
        return self.ask_answer

    async def approve(self, req):
        return True


class RecordingSink:
    def __init__(self):
        self.events = []

    def emit(self, kind, payload):
        self.events.append((kind, payload))

    def kinds(self):
        return [k for k, _ in self.events]


async def _noop(*a, **k):
    pass


# ------------------------------------------------------------------ #
# verify() — static method tests
# ------------------------------------------------------------------ #
class TestVerify:
    def test_navigate_url_changed(self):
        pre = _obs(url="about:blank")
        post = _obs(url="http://127.0.0.1:5000")
        action = AgentAction(type=ActionType.NAVIGATE, target="http://127.0.0.1:5000")
        assert OrbitAgent.verify("goal", action, pre, post) is True

    def test_navigate_url_unchanged(self):
        pre = _obs(url="http://same.com")
        post = _obs(url="http://same.com")
        action = AgentAction(type=ActionType.NAVIGATE, target="http://other.com")
        assert OrbitAgent.verify("goal", action, pre, post) is False

    def test_click_summary_changed(self):
        pre = _obs(summary="5 orders pending")
        post = _obs(summary="4 orders pending")
        action = AgentAction(type=ActionType.CLICK, target="Process button")
        assert OrbitAgent.verify("goal", action, pre, post) is True

    def test_click_url_changed(self):
        pre = _obs(url="http://a.com", summary="same")
        post = _obs(url="http://b.com", summary="same")
        action = AgentAction(type=ActionType.CLICK, target="Link")
        assert OrbitAgent.verify("goal", action, pre, post) is True

    def test_click_elements_changed(self):
        pre = _obs(elements=["'Process' button"])
        post = _obs(elements=["'Fulfil' button"])
        action = AgentAction(type=ActionType.CLICK, target="Process")
        assert OrbitAgent.verify("goal", action, pre, post) is True

    def test_click_nothing_changed(self):
        pre = _obs()
        post = _obs()  # Same URL, summary, elements
        action = AgentAction(type=ActionType.CLICK, target="Process")
        assert OrbitAgent.verify("goal", action, pre, post) is False

    def test_type_always_trusted(self):
        pre = _obs()
        post = _obs()
        action = AgentAction(type=ActionType.TYPE, target="input", value="hello")
        assert OrbitAgent.verify("goal", action, pre, post) is True

    def test_select_always_trusted(self):
        pre = _obs()
        post = _obs()
        action = AgentAction(type=ActionType.SELECT, target="dropdown", value="option1")
        assert OrbitAgent.verify("goal", action, pre, post) is True

    def test_scroll_always_trusted(self):
        pre = _obs()
        post = _obs()
        action = AgentAction(type=ActionType.SCROLL, target="down")
        assert OrbitAgent.verify("goal", action, pre, post) is True

    def test_back_url_changed(self):
        pre = _obs(url="http://a.com/page2")
        post = _obs(url="http://a.com/page1")
        action = AgentAction(type=ActionType.BACK)
        assert OrbitAgent.verify("goal", action, pre, post) is True

    def test_back_url_unchanged(self):
        pre = _obs(url="http://same.com")
        post = _obs(url="http://same.com")
        action = AgentAction(type=ActionType.BACK)
        assert OrbitAgent.verify("goal", action, pre, post) is False


# ------------------------------------------------------------------ #
# Recovery — consecutive failures trigger user help
# ------------------------------------------------------------------ #
def test_recovery_asks_user_after_max_failures():
    """After _MAX_CONSECUTIVE_FAILURES, the agent asks the user for help."""
    # Need enough actions: _MAX_CONSECUTIVE_FAILURES clicks that fail + FINISH
    actions = [
        AgentAction(type=ActionType.CLICK, target="broken button")
    ] * (_MAX_CONSECUTIVE_FAILURES + 1) + [
        AgentAction(type=ActionType.FINISH, reason="done"),
    ]
    planner = ScriptedPlanner(actions)
    gateway = RecordingGateway(ask_answer="try the other button")
    sink = RecordingSink()

    # Browser returns same observation every time (verify will fail for CLICK)
    same_obs = _obs()
    browser = MagicMock()
    browser.start = _noop
    browser.stop = _noop
    browser.observe = lambda *a, **k: _make_coro(same_obs)
    browser.execute = lambda *a, **k: _make_coro(
        ActionResult(success=True, message="ok", observation=same_obs)
    )

    agent = OrbitAgent(browser, gateway, sink, max_steps=20, planner=planner)
    outcome = asyncio.run(agent.run("Do something"))

    # The agent should have asked the user for help
    assert len(gateway.ask_calls) >= 1
    assert "failed to make progress" in gateway.ask_calls[0]
    assert "recover" in sink.kinds()


def test_recovery_counter_resets_on_success():
    """A successful action resets the consecutive failure counter."""
    # CLICK (fails) -> TYPE (succeeds, trusted) -> CLICK (fails) -> FINISH
    # Only 1 + 1 = 2 failures, below threshold, so no ask
    actions = [
        AgentAction(type=ActionType.CLICK, target="button"),  # fails
        AgentAction(type=ActionType.TYPE, target="input", value="x"),  # succeeds (trusted)
        AgentAction(type=ActionType.CLICK, target="button"),  # fails (but counter reset)
        AgentAction(type=ActionType.FINISH, reason="done"),
    ]
    planner = ScriptedPlanner(actions)
    gateway = RecordingGateway()
    sink = RecordingSink()

    same_obs = _obs()
    browser = MagicMock()
    browser.start = _noop
    browser.stop = _noop
    browser.observe = lambda *a, **k: _make_coro(same_obs)
    browser.execute = lambda *a, **k: _make_coro(
        ActionResult(success=True, message="ok", observation=same_obs)
    )

    agent = OrbitAgent(browser, gateway, sink, max_steps=20, planner=planner)
    outcome = asyncio.run(agent.run("Do something"))

    assert outcome == "done"
    # Should NOT have asked the user (only 1 consecutive failure at a time)
    assert len(gateway.ask_calls) == 0


async def _make_coro(val):
    return val
