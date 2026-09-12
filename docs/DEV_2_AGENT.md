# Dev 2 — Build the Agent Layer

**Your mission: make the brain in `orbit/agent/loop.py` real.** When you're done, a
plain-English goal becomes a sequence of browser actions, the agent asks when it's
unsure, pauses before anything consequential, and recovers when the page changes.

You build the two brain methods in **`OrbitAgent`**: `decide()` and `verify()`.
You edit **only `orbit/agent/` and `orbit/control/`**. You can build the whole
thing against the **mock browser + console human** before Dev 1 and Dev 3 finish.

---

## Build this with Claude Code

From the repo root, launch Claude Code:

```bash
claude
```

- The root `CLAUDE.md` plus the nested `orbit/agent/CLAUDE.md` load automatically
  as you work — Claude Code already knows your layer, your constraints, and the
  contract.
- Point it at this playbook and let it work step by step:
  > "Read docs/DEV_2_AGENT.md and do Build step 1. After each step, run /verify and /commit."
- Project slash commands: `/verify`, `/new-branch dev2 clarification-loop`, `/commit`,
  `/sync`, `/run-portal`.
- **Shared Claude account:** one account across all three of you means shared Claude
  Code usage limits *and* shared agent-LLM rate limits — and you call the model on
  every step. Keep sessions focused; if you hit a limit, pause and let it recover.

## Setup (5 min)

```bash
git clone https://github.com/bethahemanth/Orbit.git && cd Orbit
git checkout main && git pull --rebase origin main
uv venv && source .venv/bin/activate         # Python >= 3.11
uv pip install -e ".[dev]"
cp .env.example .env                          # paste the SHARED ANTHROPIC_API_KEY, set ORBIT_DEV_TAG=dev2
python -m orbit.main "Process today's 5 orders"   # runs today with a stub planner
```

**Shared Claude account — you call it on every step, so you use the quota most.**
It's one key for all three of you. While iterating: keep `max_steps` low, print and
reuse the model's raw output instead of re-running, and say in chat before a heavy
test run. On 429s, back off. The model id is `orbit.config.settings.model`.

The loop skeleton (observe→reason→act→verify→recover, plus clarify + approval
routing) is already wired in `orbit/agent/loop.py`. You only fill in `decide()` and
`verify()`.

---

## Build step 1 — a rule-based `decide()` (target: 0:00–0:25)

Get the loop *doing something* before adding the LLM. Return real actions from the
observation so you can see navigate/click happen against the mock.

**Build.** In `decide()`:
```python
async def decide(self, goal, obs):
    if "127.0.0.1:5000" not in obs.url:
        return AgentAction(ActionType.NAVIGATE, target="http://127.0.0.1:5000",
                           reason="open the portal")
    if any("process" in e.lower() for e in obs.interactive_elements):
        return AgentAction(ActionType.CLICK, target="the 'Process' button",
                           reason="process the next order")
    return AgentAction(ActionType.FINISH, reason="nothing left to process")
```

**Verify.** `python -m orbit.main "Process today's 5 orders"` — the trace should now
show OBSERVE → navigate → click, not just an instant FINISH.

**Commit.** `feat(agent): rule-based planner drives the mock loop`

---

## Build step 2 — the real LLM planner (target: 0:25–1:00)

Now make `decide()` ask the shared Claude account for the next action. Prompt the
model with the goal + observation and require **one** action back as JSON, then
parse it into an `AgentAction`.

**Build (pattern — adapt to your version):**
```python
from browser_use import ChatAnthropic          # or the `anthropic` SDK directly
from orbit.config import settings

SYS = """You control a web browser. Given a GOAL and the current PAGE, output the
SINGLE next action as JSON: {"type": one of navigate|click|type|select|scroll|back|ask_user|finish,
"target": semantic description (role/visible text/meaning, NOT a css selector),
"value": text to type/select or the question for ask_user, "reason": short why,
"risk": "safe" or "consequential"}.
Rules: use ask_user when the target is ambiguous. Mark submit/purchase/delete/send as consequential."""

async def decide(self, goal, obs):
    llm = ChatAnthropic(model=settings.model)          # uses the shared key
    prompt = f"GOAL:\n{goal}\n\nPAGE:\nurl={obs.url}\n{obs.page_summary}\nelements={obs.interactive_elements}"
    raw = await llm.ainvoke([{"role":"system","content":SYS},{"role":"user","content":prompt}])
    data = _parse_json(raw)                              # strip ``` fences, json.loads
    return AgentAction(type=ActionType(data["type"]), target=data.get("target"),
                       value=data.get("value"), reason=data.get("reason",""),
                       risk=RiskLevel(data.get("risk","safe")))
```

Write `_parse_json` defensively (models sometimes wrap JSON in ``` fences or prose).

**Verify.** Run against the mock — the actions now come from Claude. Watch the
REASON events in the trace explain each choice.

**Commit.** `feat(agent): LLM planner via shared Claude account`

**Claude prompt:** *"Write a robust `_parse_json(text)` that extracts the first JSON
object from an LLM reply that may include ``` fences or extra prose, and raises a
clear error if none is found."*

---

## Build step 3 — clarification + approval (target: 1:00–1:40)

These are already **routed** by the loop — your job is to make `decide()` *emit*
them correctly.

- **Ambiguity → ask.** For "Process John's order" when the page shows three Johns,
  return `AgentAction(ActionType.ASK_USER, value="Which John? Smith, Carter, or Diaz?")`.
  The loop calls `gateway.ask(...)`, appends the answer to the goal, and continues.
- **Consequential → approve.** Mark submit/purchase/delete/send with
  `risk=RiskLevel.CONSEQUENTIAL`. The loop automatically calls `gateway.approve(...)`
  before executing and skips the action if rejected.

**Verify.**
```bash
python -m orbit.main "Process John's order"     # should ask which John (console prompt)
```
Then force a consequential action and confirm it pauses for `Approve? [y/N]`.

**Commit.** `feat(agent): emit clarification + mark consequential actions`

---

## Build step 4 — `verify()` + recovery (target: 1:40–2:20)

**Build.** After each action, check the new observation actually reflects progress;
return `False` to trigger the loop's recovery branch (re-observe, re-plan, or ask).

```python
def verify(self, goal, action, obs):
    if action.type == ActionType.CLICK and "processed" in obs.page_summary.lower():
        return True
    # add an LLM check for harder cases: "did PAGE move us toward GOAL? yes/no"
    return True
```

Then flesh out the recovery branch in `run()` so a changed label/layout doesn't
kill the task — re-observe and let `decide()` pick again.

**Verify.** Ask Dev 3 to flip the button Process→Fulfil; the run should recover and
still complete instead of erroring.

**Commit.** `feat(agent): verification + recovery path`

---

## Build step 5 — go live end-to-end (target: 2:20–3:00)

You own the wiring in `orbit/main.py` (shared file — do this near the end and
announce it). Swap the mock for the real pieces:

```python
browser = BrowserUseController(headless=settings.headless)   # Dev 1
from orbit.ui.activity import WebGateway, WebActivitySink     # Dev 3
agent = OrbitAgent(browser, WebGateway(), WebActivitySink())
```

**Verify (your definition of done):**
- 5 orders processed end-to-end against Dev 1's real browser.
- Ambiguous goal asks; consequential step waits for approval.
- Renamed control recovers.
- The same agent also completes a task on one real website.

---

## Git — the short version (full rules: `docs/GIT_WORKFLOW.md`)

```bash
git checkout -b feat/dev2-clarification-loop     # branch name: <type>/dev2-<what>
# ...small commits per step...
git fetch origin && git rebase origin/main       # rebase onto main, never merge it in
git push --force-with-lease                       # open a PR into main
```
Edit **`orbit/agent/` and `orbit/control/`**; touch `orbit/main.py` last (shared).
Need a new field on `AgentAction`/`Observation`? That's `contracts.py` (the seam):
announce it, keep it additive, land a tiny `chore(contracts)` PR, tell the team to
rebase. Keep `pytest -q` green.
