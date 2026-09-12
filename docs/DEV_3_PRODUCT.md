# Dev 3 — Build the Product / Demo Layer

**Your mission: build the stage the agent performs on.** When you're done there's a
business portal the agent operates, a live panel showing observe→action→result→
verify as it runs, an Approve|Reject control for risky steps, and a rehearsed
90-second demo.

You build the portal (`orbit/portal/`) and the UI (`orbit/ui/activity.py`). You
edit **only `orbit/portal/` and `orbit/ui/`**. Most of your work needs **no LLM**,
so you'll barely touch the shared quota.

---

## Build this with Claude Code

From the repo root, launch Claude Code:

```bash
claude
```

- The root `CLAUDE.md` plus the nested `orbit/portal/CLAUDE.md` and
  `orbit/ui/CLAUDE.md` load automatically as you work — Claude Code already knows
  your layer, your constraints, and the contract.
- Point it at this playbook and let it work step by step:
  > "Read docs/DEV_3_PRODUCT.md and do Build step 1. After each step, run /verify and /commit."
- Project slash commands: `/verify`, `/new-branch dev3 order-portal`, `/commit`,
  `/sync`, `/run-portal`.
- **Shared Claude account:** all three of you are on one account, so Claude Code
  usage limits are shared. Coordinate long sessions; if you hit a limit, pause and
  let it recover. (Most of your work needs no LLM, so you'll use the least.)

## Setup (5 min)

```bash
git clone https://github.com/bethahemanth/Orbit.git && cd Orbit
git checkout main && git pull --rebase origin main
uv venv && source .venv/bin/activate         # Python >= 3.11
uv pip install -e ".[dev]"
cp .env.example .env                          # paste the SHARED ANTHROPIC_API_KEY, set ORBIT_DEV_TAG=dev3
python -m orbit.portal.app                    # portal already runs @ http://127.0.0.1:5000
```

The portal is scaffolded: an orders table, a semantic **Process** button, a search
box, a `RENAME_BUTTON` toggle, and three "John" customers (for the ambiguity demo).
Your job is to finish it, build the live UI, and make the demo bulletproof.

---

## Build step 1 — finish the business portal (target: 0:00–0:40)

**Build.** In `orbit/portal/`:
- Keep it **generic** (a real-looking orders workflow) — the agent must *discover*
  it, not be hard-wired to it.
- Add a confirmation step so there's a genuinely *consequential* action for the
  approval demo (e.g. a "Confirm & submit" page before an order is finalised).
- Wire the `RENAME_BUTTON` toggle (Process→Fulfil) and add one field-move variation
  for the semantic-recovery demo.

**Verify.**
```bash
python -m orbit.portal.app       # click Process, watch a row flip to 'processed'
```
Ask Dev 1 to point `observe()` at it and confirm the buttons show up as semantic
elements.

**Commit.** `feat(portal): orders workflow + confirm step + rename toggle`

**Claude prompt:** *"Add a two-step confirm flow to this Flask app: clicking Process
goes to a confirmation page with a 'Confirm & submit' button that finalises the
order. Keep it minimal."*

---

## Build step 2 — the live activity feed (target: 0:40–1:30)

The agent emits every step to your `ActivitySink`. Render it live.

**Build.** In `orbit/ui/activity.py`, implement `WebActivitySink.emit()` to push
events, and add a route in the portal that streams them (Server-Sent Events is the
simplest for a hackathon; polling also fine):

```python
# orbit/ui/activity.py
import queue
class WebActivitySink(ActivitySink):
    def __init__(self): self.q = queue.Queue()
    def emit(self, kind, payload): self.q.put({"kind": kind, **payload})
```

```python
# a route in orbit/portal/app.py
from flask import Response
@app.route("/activity/stream")
def stream():
    def gen():
        while True:
            evt = SINK.q.get()
            yield f"data: {json.dumps(evt)}\n\n"
    return Response(gen(), mimetype="text/event-stream")
```

Add a panel in the template that subscribes with `new EventSource('/activity/stream')`
and appends each event as a line: `OBSERVE …`, `REASON …`, `ACT …`, `VERIFY …`.

**Verify.** Run the wired loop and watch lines appear live in the browser as it acts.

**Commit.** `feat(ui): live activity feed via SSE`

**Claude prompt:** *"Give me the JS for a page that opens an EventSource on
`/activity/stream` and appends each JSON event to a scrolling log panel, colour-coded
by the `kind` field."*

---

## Build step 3 — the approval + clarification UI (target: 1:30–2:10)

The agent reaches the human through your `WebGateway`. Make the two calls show up
in the browser and return the person's choice.

**Build.** Implement `WebGateway.ask()` and `.approve()` in `orbit/ui/activity.py`
backed by a request the UI can answer:
- `ask(request)` → render the question (+ options) in the panel, block until the
  user submits an answer, return the string.
- `approve(request)` → render the pending action with **Approve** / **Reject**
  buttons, block until clicked, return `True/False`.

A simple pattern: put the pending question/approval in a shared object, expose
`GET /gateway/pending` and `POST /gateway/answer`, and have `ask/approve` await the
posted answer (use an `asyncio.Event` or poll a `queue`).

**Verify.**
```bash
# with Dev 2's loop wired to WebGateway:
python -m orbit.main --real "Process John's order"   # UI shows "Which John?" and waits
```
Then trigger the confirm step and confirm **Approve|Reject** appears and gates it.

**Commit.** `feat(ui): web clarification + approval gateway`

---

## Build step 4 — demo hardening + rehearse (target: 2:10–3:00)

- Clean, readable activity log; sensible colours; auto-scroll.
- Two website contexts ready: the portal **and** one real site (coordinate with
  Dev 1).
- Rehearse the six beats in `demo/demo_script.md` until the final take is reliable.

**Your definition of done:**
- Portal runs; agent processes orders through it.
- Activity panel shows the live trace during a run.
- A consequential step shows Approve|Reject and waits.
- Ambiguous goal shows a clarification question in the UI.
- Renamed/moved control still works.

---

## Git — the short version (full rules: `docs/GIT_WORKFLOW.md`)

```bash
git checkout -b feat/dev3-order-portal           # branch name: <type>/dev3-<what>  (also demo/dev3-...)
# ...small commits per step...
git fetch origin && git rebase origin/main       # rebase onto main, never merge it in
git push --force-with-lease                       # open a PR into main
```
Edit **only `orbit/portal/` and `orbit/ui/`**. Need a new event kind or field?
That's `contracts.py` (the shared seam): announce it, keep it additive, land a tiny
`chore(contracts)` PR, tell the team to rebase. Keep `pytest -q` green.
