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


class OrbitAgent:
    def __init__(
        self,
        browser: BrowserController,
        gateway: HumanGateway,
        activity: ActivitySink,
        max_steps: int = 25,
    ) -> None:
        self.browser = browser
        self.gateway = gateway
        self.activity = activity
        self.max_steps = max_steps

    async def run(self, goal: str) -> str:
        """Drive `goal` to completion. Returns a short outcome string."""
        self.activity.emit("goal", {"goal": goal})
        await self.browser.start()
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
                    continue

                if action.risk == RiskLevel.CONSEQUENTIAL:
                    ok = await self.gateway.approve(
                        ApprovalRequest(action=action,
                                        summary=action.reason or "Consequential step")
                    )
                    self.activity.emit("approval", {"granted": ok})
                    if not ok:
                        continue

                result = await self.browser.execute(action)
                self.activity.emit("act", {"success": result.success, "msg": result.message})

                if not self.verify(goal, action, result.observation or obs):
                    self.activity.emit("recover", {"note": "verification failed, retrying"})
                    # TODO(dev2): real recovery — re-observe, re-plan, or ask.
                    continue

            return "max_steps_reached"
        finally:
            await self.browser.stop()

    # ------------------------------------------------------------------ #
    # The two brain methods. Start rule-based, then swap in the LLM.
    # ------------------------------------------------------------------ #
    async def decide(self, goal: str, obs: Observation) -> AgentAction:
        """REASON: pick the next action from the goal + current page.

        TODO(dev2): call the shared Claude account (ChatAnthropic via
        orbit.config.settings.model) with the goal + observation and parse a
        single AgentAction out. Set risk=CONSEQUENTIAL for submit/purchase/
        delete/send. Emit ASK_USER when the target is ambiguous (e.g. 3 Johns).

        The stub below just finishes, so the loop is runnable end-to-end today.
        """
        return AgentAction(type=ActionType.FINISH, reason="stub: replace with LLM planner")

    def verify(self, goal: str, action: AgentAction, obs: Observation) -> bool:
        """VERIFY: did the last action move us toward the goal?

        TODO(dev2): compare expected vs. actual page state. Return False to
        trigger recovery. Stub trusts every action for now.
        """
        return True
