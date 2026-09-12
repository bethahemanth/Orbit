"""
orbit.agent.loop   ---  DEV 2 (Agent) owns this file.
====================================================

Responsibility (spec Section 8, Member 2): the control loop and action
decisioning around the Browser Use runtime.

    GOAL -> OBSERVE -> REASON -> ACT -> OBSERVE -> VERIFY -> CONTINUE/RECOVER -> COMPLETE
    (spec Section 5)

This layer decides *what* to do. It:
  * turns a natural-language goal into the next AgentAction (REASON),
  * asks for clarification when intent/target is ambiguous,
  * routes CONSEQUENTIAL actions through human approval,
  * verifies the result and recovers when the page changed.

It talks to the browser through `BrowserController`, and to the human through
`HumanGateway`, and reports every step to `ActivitySink`. It never touches
Chrome or the UI directly — only the contracts.
"""

from __future__ import annotations

from orbit.agent.planner import LLMPlanner, Planner, RulePlanner
from orbit.config import has_llm, settings
from orbit.contracts import (
    ActionType,
    ActivitySink,
    AgentAction,
    ApprovalRequest,
    BrowserController,
    ClarificationRequest,
    HumanGateway,
    Observation,
    RiskLevel,
)

# Maximum consecutive verification failures before asking the user for help.
_MAX_CONSECUTIVE_FAILURES = 3


class OrbitAgent:
    def __init__(
        self,
        browser: BrowserController,
        gateway: HumanGateway,
        activity: ActivitySink,
        max_steps: int = 25,
        planner: Planner | None = None,
    ) -> None:
        self.browser = browser
        self.gateway = gateway
        self.activity = activity
        self.max_steps = max_steps
        self.planner = planner or self._default_planner()

    @staticmethod
    def _default_planner() -> Planner:
        """LLM when a key is configured, rules when there isn't one.

        Keeps the promise in the README: a fresh clone runs offline with no key.
        """
        return LLMPlanner() if has_llm() else RulePlanner(settings.portal_url)

    async def run(self, goal: str) -> str:
        """Drive `goal` to completion. Returns a short outcome string."""
        self.activity.emit("goal", {"goal": goal})
        await self.browser.start()
        consecutive_failures = 0
        try:
            for step in range(self.max_steps):
                obs = await self.browser.observe()
                self.activity.emit("observe", {"step": step, "url": obs.url,
                                                "summary": obs.page_summary})

                action = await self.decide(goal, obs)
                self.activity.emit("reason", {"step": step, "action": action.type.value,
                                              "target": action.target, "why": action.reason})

                if action.type == ActionType.FINISH:
                    self.activity.emit("complete", {"step": step})
                    return "done"

                if action.type == ActionType.ASK_USER:
                    answer = await self.gateway.ask(
                        ClarificationRequest(question=action.value or action.reason)
                    )
                    self.activity.emit("clarify", {"answer": answer})
                    goal = f"{goal}\n[clarification] {answer}"
                    consecutive_failures = 0
                    continue

                if action.risk == RiskLevel.CONSEQUENTIAL:
                    ok = await self.gateway.approve(
                        ApprovalRequest(action=action,
                                        summary=action.reason or "Consequential step")
                    )
                    self.activity.emit("approval", {"granted": ok})
                    if not ok:
                        continue

                # Capture pre-action state for verification comparison.
                pre_obs = obs

                result = await self.browser.execute(action)
                self.activity.emit("act", {"success": result.success, "msg": result.message})

                post_obs = result.observation or obs

                if not self.verify(goal, action, pre_obs, post_obs):
                    consecutive_failures += 1
                    self.activity.emit("recover", {
                        "note": "verification failed",
                        "consecutive_failures": consecutive_failures,
                    })

                    if consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
                        # Too many failures in a row — ask the user for help.
                        answer = await self.gateway.ask(
                            ClarificationRequest(
                                question=(
                                    f"I've failed to make progress {consecutive_failures} "
                                    f"times in a row. The last action was "
                                    f"'{action.type.value}' on '{action.target}'. "
                                    f"What should I try instead?"
                                ),
                            )
                        )
                        self.activity.emit("clarify", {"answer": answer})
                        goal = f"{goal}\n[recovery guidance] {answer}"
                        consecutive_failures = 0
                    continue
                else:
                    consecutive_failures = 0

            return "max_steps_reached"
        finally:
            await self.browser.stop()

    # ------------------------------------------------------------------ #
    # The two brain methods. Start rule-based, then swap in the LLM.
    # ------------------------------------------------------------------ #
    async def decide(self, goal: str, obs: Observation) -> AgentAction:
        """REASON: pick the next action from the goal + current page.

        Delegates to whichever `Planner` this agent was built with — the LLM
        planner when a key is configured, the rule-based one offline. The loop
        itself stays planner-agnostic on purpose: swapping the brain must not
        mean touching the control flow.
        """
        return await self.planner.next_action(goal, obs)

    @staticmethod
    def verify(
        goal: str,
        action: AgentAction,
        pre_obs: Observation,
        post_obs: Observation,
    ) -> bool:
        """VERIFY: did the last action move us toward the goal?

        Uses lightweight heuristics so verification doesn't cost an LLM call on
        every step. Returns False to trigger the recovery branch in `run()`.

        Heuristics by action type:
          NAVIGATE  — URL must have changed.
          CLICK     — page_summary or URL should differ (the page reacted).
          TYPE      — trusted (typing doesn't change the page until submit).
          SELECT    — trusted (same reasoning as TYPE).
          SCROLL    — trusted (scroll is exploratory, not a state change).
          BACK      — URL should have changed.
          Others    — trusted by default.
        """
        atype = action.type

        if atype == ActionType.NAVIGATE:
            # Did the URL actually change?
            return post_obs.url != pre_obs.url

        if atype == ActionType.CLICK:
            # Something on the page should have changed.
            url_changed = post_obs.url != pre_obs.url
            summary_changed = post_obs.page_summary != pre_obs.page_summary
            elements_changed = post_obs.interactive_elements != pre_obs.interactive_elements
            return url_changed or summary_changed or elements_changed

        if atype == ActionType.BACK:
            return post_obs.url != pre_obs.url

        # TYPE, SELECT, SCROLL, and anything else — trust the browser.
        return True
