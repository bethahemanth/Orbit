"""
orbit.agent.planner   ---  DEV 2 (Agent) owns this file.
========================================================

The REASON half of the loop: given a GOAL and an `Observation`, produce the
single next `AgentAction`.

Two planners live here, behind the same tiny interface:

    RulePlanner  -- no LLM, no key, deterministic. Keeps a fresh clone runnable
                    offline and gives the loop something to do while iterating.
    LLMPlanner   -- the real brain. Asks the model (whatever
                    `orbit.config.make_llm()` returns) for one action as JSON.

`OrbitAgent.decide()` picks between them: LLM when a key is configured, rules
otherwise. That is what keeps `pytest -q` green on a machine with no `.env`.

Targets produced here are always **semantic** ("the 'Process' button"), never a
CSS selector — Dev 1's browser layer resolves them to real elements.
"""

from __future__ import annotations

from typing import Protocol

from orbit.contracts import ActionType, AgentAction, Observation, RiskLevel


class Planner(Protocol):
    async def next_action(self, goal: str, obs: Observation) -> AgentAction: ...


# --------------------------------------------------------------------------- #
# Rule-based planner — the offline fallback.
# --------------------------------------------------------------------------- #
class RulePlanner:
    """Deterministic planner: open the portal, then click through the work.

    Deliberately dumb. It exists so the loop is observable end-to-end without a
    key, not to be clever — the moment a key is present, `LLMPlanner` takes over
    and this is never consulted. It keeps just enough state to stop instead of
    clicking the same control forever.
    """

    def __init__(self, portal_url: str, max_repeats: int = 5) -> None:
        self.portal_url = portal_url
        self.max_repeats = max_repeats
        self._seen: dict[str, int] = {}

    async def next_action(self, goal: str, obs: Observation) -> AgentAction:
        if self.portal_url not in obs.url:
            return AgentAction(
                type=ActionType.NAVIGATE,
                target=self.portal_url,
                reason="not on the portal yet — open it",
            )

        target = self._first_actionable(obs)
        if target is None:
            return AgentAction(
                type=ActionType.FINISH,
                reason="no actionable control left on the page",
            )

        # Guard against looping on a page that never changes (e.g. the mock).
        count = self._seen.get(target, 0) + 1
        self._seen[target] = count
        if count > self.max_repeats:
            return AgentAction(
                type=ActionType.FINISH,
                reason=f"{target!r} stopped changing the page after {self.max_repeats} tries",
            )

        return AgentAction(
            type=ActionType.CLICK,
            target=target,
            reason="advance the visible workflow",
            risk=self._risk_of(target),
        )

    @staticmethod
    def _first_actionable(obs: Observation) -> str | None:
        """Pick the first element that looks like it advances the task."""
        for verb in ("process", "fulfil", "fulfill", "confirm", "submit"):
            for element in obs.interactive_elements:
                if verb in element.lower():
                    return element
        return None

    @staticmethod
    def _risk_of(target: str) -> RiskLevel:
        return classify_risk(target)


# --------------------------------------------------------------------------- #
# Risk classification — shared by both planners.
# --------------------------------------------------------------------------- #
#: Words that mean "this changes the world", not "this looks around".
CONSEQUENTIAL_WORDS = (
    "submit", "confirm", "purchase", "buy", "pay", "checkout", "order",
    "delete", "remove", "cancel", "send", "publish", "approve", "finalise",
    "finalize",
)


def classify_risk(text: str | None) -> RiskLevel:
    """CONSEQUENTIAL if the control's own words say it commits something.

    The agent may also mark risk itself; this is the backstop so a model that
    forgets to set `risk` still can't silently submit an order.
    """
    if not text:
        return RiskLevel.SAFE
    lowered = text.lower()
    if any(word in lowered for word in CONSEQUENTIAL_WORDS):
        return RiskLevel.CONSEQUENTIAL
    return RiskLevel.SAFE
