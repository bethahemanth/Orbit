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


# --------------------------------------------------------------------------- #
# LLM planner — the real brain.
# --------------------------------------------------------------------------- #
SYSTEM_PROMPT = """You control a web browser to complete a goal for a user.

Given the GOAL and the current PAGE, output the SINGLE next action as JSON:
{"type": one of navigate|click|type|select|scroll|back|ask_user|finish,
 "target": semantic description of the element (role / visible text / meaning,
           NEVER a css selector, NEVER an index),
 "value": text to type or select, or the QUESTION when type is ask_user,
 "reason": one short sentence on why this action,
 "risk": "safe" or "consequential"}

Rules:
- Output JSON only. No prose, no code fences.
- Use "ask_user" when the goal is ambiguous about WHICH item to act on — for
  example the goal names "John" and the page shows three different Johns. Ask
  instead of guessing. Put the question in "value" and list the options in it.
- Mark submit / purchase / pay / delete / send / confirm as "consequential".
  Everything else (navigating, reading, typing a draft) is "safe".
- Use "finish" when the GOAL is already satisfied by what the PAGE shows.
- Prefer the action that makes visible progress on the page you were given."""


class LLMPlanner:
    """Asks the model for exactly one next action and parses it.

    Holds no browser state — it only ever sees the goal and the latest
    observation, which is what keeps the agent honest about reacting to the
    live page instead of replaying a memorised script.
    """

    def __init__(self, llm=None, max_tokens: int = 512) -> None:
        self._llm = llm
        self.max_tokens = max_tokens

    @property
    def llm(self):
        # Built lazily so importing the agent never requires a key.
        if self._llm is None:
            from orbit.config import make_llm
            self._llm = make_llm()
        return self._llm

    async def next_action(self, goal: str, obs: Observation) -> AgentAction:
        prompt = (
            f"GOAL:\n{goal}\n\n"
            f"PAGE:\nurl: {obs.url}\ntitle: {obs.title}\n"
            f"{obs.page_summary}\n\n"
            f"INTERACTIVE ELEMENTS:\n"
            + "\n".join(f"- {e}" for e in obs.interactive_elements)
        )
        raw = await self.llm.ainvoke(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=self.max_tokens,
        )
        return self._to_action(parse_json(raw))

    @staticmethod
    def _to_action(data: dict) -> AgentAction:
        try:
            action_type = ActionType(str(data["type"]).strip().lower())
        except (KeyError, ValueError) as exc:
            raise ValueError(f"model returned an unusable action type: {data!r}") from exc

        target = data.get("target")
        value = data.get("value")

        # Safety backstop: ask_user MUST have a question in `value`.
        if action_type is ActionType.ASK_USER and not value:
            value = data.get("reason") or "Could you clarify what you'd like me to do?"

        # Trust the model's risk, but never downgrade below what the words say:
        # a model that forgets `risk` must not be able to submit silently.
        stated = str(data.get("risk", "safe")).strip().lower()
        risk = RiskLevel.CONSEQUENTIAL if stated == "consequential" else RiskLevel.SAFE
        if risk is RiskLevel.SAFE and action_type is ActionType.CLICK:
            risk = classify_risk(target)

        return AgentAction(
            type=action_type,
            target=target,
            value=value,
            reason=str(data.get("reason", "")),
            risk=risk,
        )


def parse_json(text: str) -> dict:
    """Extract the first JSON object from an LLM reply.

    Models wrap JSON in ``` fences, prefix it with "Here's the action:", or add
    a trailing explanation. Scanning for the first balanced {...} survives all
    three without a regex that breaks on nested braces.
    """
    import json

    if not text or not text.strip():
        raise ValueError("model returned an empty reply")

    depth = 0
    start = -1
    in_string = False
    escaped = False

    for i, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = i
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and start != -1:
                return json.loads(text[start : i + 1])

    raise ValueError(f"no JSON object found in model reply: {text[:200]!r}")


# --------------------------------------------------------------------------- #
# LLM-based verification — optional, costs one extra call per step.
# --------------------------------------------------------------------------- #
VERIFY_PROMPT = """You are verifying whether a browser action made progress toward a goal.

Given the GOAL, the ACTION that was just taken, and the resulting PAGE state,
answer with EXACTLY one word: "yes" or "no".

- "yes" = the page state shows the action moved us closer to completing the goal.
- "no"  = the page looks unchanged, the action failed, or we moved further away.

Do not explain. One word only."""


async def llm_verify_progress(
    llm,
    goal: str,
    action: AgentAction,
    obs: Observation,
) -> bool:
    """Ask the LLM whether the last action advanced the goal.

    Returns True if the model says yes (or if the call fails — we don't want
    a verification glitch to block the whole run).
    """
    prompt = (
        f"GOAL:\n{goal}\n\n"
        f"ACTION TAKEN:\n{action.type.value} -> {action.target or '(none)'}\n"
        f"reason: {action.reason}\n\n"
        f"RESULTING PAGE:\nurl: {obs.url}\ntitle: {obs.title}\n"
        f"{obs.page_summary}\n"
        f"elements: {obs.interactive_elements}"
    )
    try:
        raw = await llm.ainvoke(
            [
                {"role": "system", "content": VERIFY_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=8,
        )
        return raw.strip().lower().startswith("yes")
    except Exception:
        # Verification failure must never kill the run.
        return True

