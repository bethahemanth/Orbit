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

### Two things you inherit from the other layers

**The model is configured centrally — nothing in your layer picks one.** The
provider and model id come from `orbit.config.make_llm()` reading `.env`
(`ORBIT_LLM_PROVIDER`, `ORBIT_MODEL`; OpenRouter optional), so `orbit/portal/` and
`orbit/ui/` must never hard-code a model, a provider, or an API key. If a demo run
needs a different model, that's an `.env` edit, not a code change.

**Keep every demo scenario browser-native.** The agent has an optional Exa web-search
tool (`orbit.agent.tools`) if a test-case task truly needs an external lookup — but
do **not** design a demo beat around it. The whole pitch is *"the browser is the
integration layer"*; a scenario the agent solves by calling a search API instead of
operating a page undercuts the thesis on stage. Portal and real-website beats stay
pure browser.

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

---

# Independent implementation context

This section expands the short playbook above into an implementation-ready contract for
dev_3_product. It is written from the current repository baseline so the module can
be built without depending on another developer's unfinished code.

## A. Baseline and boundaries

At the time this plan is written:

- orbit/portal/app.py owns a Flask app, GET /, POST /process/<order_id>, and the
  RENAME_BUTTON label toggle.
- orbit/portal/orders.py owns a process-local ORDERS list containing five orders,
  including John Smith, John Carter, and John Diaz.
- orbit/portal/templates/index.html renders a search form, an orders table, and a
  form with one Process-order submit button per pending row.
- orbit/ui/activity.py has WebActivitySink.events but does not publish events to a
  browser. WebGateway.ask and WebGateway.approve are stubs.
- orbit/agent/loop.py is the producer of activity events and the caller of the
  gateway methods. It does not know Flask or any UI implementation.
- orbit/main.py currently constructs ConsoleGateway and ConsoleActivitySink. The
  final shared wiring belongs to Dev 2; the product layer must also expose a
  same-process portal run endpoint so the UI can be demonstrated independently.

The product module may edit only orbit/portal/, orbit/ui/, their templates, and
Dev-3-owned tests/documentation. Do not edit orbit/browser/, orbit/agent/, or
orbit/control/. Do not silently edit contracts.py, main.py, or config.py.

## B. Architecture at the product seam

The product layer sits on these stable protocols from orbit/contracts.py:

### Team responsibility map

| developer | owns | deliverable and non-responsibilities |
|---|---|---|
| dev_1_browser | orbit/browser/ | Browser Use/Chrome lifecycle, semantic observation, and execution of every AgentAction; does not decide tasks or render UI. |
| dev_2_agent | orbit/agent/ and orbit/control/ | OBSERVE → REASON → ACT → VERIFY loop, LLM planning, clarification, approval routing, and recovery; owns final shared main.py wiring. |
| dev_3_product | orbit/portal/ and orbit/ui/ | Generic business portal, confirmation workflow, activity stream, web gateway, run/demo surface, and product tests; does not implement browser or agent logic. |

All three layers meet through contracts.py. The shared file is intentionally small:
it contains the action/observation/result dataclasses and the BrowserController,
HumanGateway, and ActivitySink protocols. The product layer must be independently
runnable against MockBrowserController and must not wait for a real LLM or Chrome.

1. BrowserController supplies start, stop, observe, and execute. The portal does
   not call these methods directly; OrbitAgent does.
2. HumanGateway supplies async ask(ClarificationRequest) -> str and async
   approve(ApprovalRequest) -> bool.
3. ActivitySink supplies synchronous emit(kind: str, payload: dict) -> None.
4. AgentAction, Observation, ActionResult, ClarificationRequest, and ApprovalRequest
   are dataclasses. Treat their fields as public input/output.

The only allowed communication path from the loop into the UI is ActivitySink and
HumanGateway. The only allowed communication path from the browser into the loop
is BrowserController. This separation is what lets the mock browser and console
defaults continue to run while the web product is incomplete.

The intended process topology is:

~~~text
Flask request thread
  ├── renders portal and polls gateway/activity endpoints
  └── accepts POST /run
        └── background thread
              └── asyncio.run(OrbitAgent.run(goal))
                    ├── shared WebActivitySink
                    ├── shared WebGateway
                    └── MockBrowserController or BrowserUseController
~~~

The sink, gateway, and run manager must be long-lived objects created once per
Flask process. Creating them inside each request disconnects the UI from the agent.

## C. Exact agent events the UI must accept

The current OrbitAgent emits the following events. Preserve these names and fields;
the UI may add presentation metadata but must not require fields the agent does not
send.

| kind | fields | rendering |
|---|---|---|
| goal | goal | run header |
| observe | step, url, summary | page snapshot |
| reason | step, action, target, why | planner decision |
| act | success, msg | browser result |
| clarify | answer | human answer |
| approval | granted | approval result |
| recover | note | retry/recovery warning |
| complete | step | terminal success |

Unknown future kinds must render as a generic log line. Payload values can be null,
so JSON serialization and template rendering must tolerate missing target, value,
why, or error fields.

The existing loop awaits the gateway before it emits clarify/approval and before it
executes a consequential action. Therefore a pending gateway object is not merely
status; it is the synchronization point that controls whether the browser proceeds.

## D. Portal state machine and requirements

### D1. Order data

Keep the existing list-of-dicts model for the hackathon. Required fields:

~~~text
id: integer, unique route key
customer: string, visible customer name
item: string, visible item description
qty: positive integer
status: "pending" or "processed"
~~~

The three John records are mandatory for the ambiguity demo. Do not replace them
with a single aggregate customer or an opaque hidden key.

### D2. Routes

Implement this route contract in orbit/portal/app.py:

| method | path | required behavior |
|---|---|---|
| GET | / | render the order list; q filters customer case-insensitively |
| POST | /process/<int:order_id> | validate pending order; redirect to /confirm/<id>; do not finalize |
| GET | /confirm/<int:order_id> | render a human-readable confirmation summary |
| POST | /confirm/<int:order_id> | validate pending order, set processed, redirect to / |
| GET | /activity/stream | SSE stream for WebActivitySink |
| GET | /gateway/pending | JSON view of the current gateway request |
| POST | /gateway/answer | validate and resolve a pending gateway request |
| POST | /run | start one background agent run in this Flask process |
| GET | /run/status | expose idle/running/finished/failed state |

Unknown order IDs return 404. Trying to process an already processed order must
return 409 or a visible no-op; it must never revert processed to pending. A second
run while one is active returns 409.

### D3. Normal workflow

The first row action is a safe selection/navigation step. The confirmation page
must contain:

- customer name, item, quantity, and current order status;
- a visible button named Confirm & submit;
- a visible way back to the orders list.

Only POST /confirm/<id> mutates status. This is the consequential browser action
that Dev 2 should mark RiskLevel.CONSEQUENTIAL. The portal must not auto-submit or
use a hidden confirmation field.

### D4. Semantic variation

RENAME_BUTTON remains a deterministic toggle that changes only the visible action
label, for example Process order to Fulfil order. The form action, order ID, and
confirmation behavior remain identical. Add one layout variation (for example,
move the search form below the table or change the action-cell position) while
keeping accessible labels and normal form controls intact. The agent must be able
to operate both layouts from visible meaning; no special browser endpoint or
selector may be introduced for the variation.

## E. WebActivitySink design

Implement WebActivitySink in orbit/ui/activity.py while continuing to satisfy
ActivitySink.emit.

Recommended fields:

~~~python
history: deque[dict[str, Any]]       # bounded, for recent/debug views
subscribers: set[queue.Queue]        # one queue per SSE client
lock: threading.Lock
max_history: int = 500
~~~

Recommended methods:

~~~python
emit(kind, payload) -> None
subscribe() -> queue.Queue
unsubscribe(q) -> None
recent() -> list[dict[str, Any]]
~~~

emit creates {"kind": kind, **payload}, appends it to bounded history, and puts a
copy on every subscriber queue under the lock. A queue must be bounded or have a
drop-oldest policy so a disconnected browser cannot grow memory without limit.
The SSE generator calls subscribe at connection time and unsubscribe in finally.

Each SSE event is framed as:

~~~text
data: {"kind":"observe","step":0,"url":"...","summary":"..."}

~~~

Use Response(generator, mimetype="text/event-stream") and disable proxy buffering
where possible with Cache-Control: no-cache and X-Accel-Buffering: no. Emit a
keep-alive comment during long idle periods. The intended demo has one browser, but
per-subscriber queues make a second tab safe and are cheap to implement.

The front-end uses EventSource('/activity/stream'), JSON.parse(event.data), and
textContent for payload display. It must auto-scroll and use a class based on kind
for color. It must render unknown event kinds as plain text.

## F. WebGateway design

WebGateway bridges an async agent loop to synchronous Flask request threads. Do not
share an asyncio.Event between event loops. Use thread-safe primitives.

### F1. Pending record

Maintain one pending record at a time:

~~~python
{
    "id": "uuid",
    "kind": "clarification" or "approval",
    "public": {...JSON-safe fields...},
    "answer_queue": queue.Queue(maxsize=1),
}
~~~

The public fields for clarification are id, kind, question, and options. The public
fields for approval are id, kind, summary, and a JSON-safe action projection with
type, target, value, and risk.

### F2. Async methods

ask(request):

1. Create a UUID and a maxsize-one answer queue.
2. Under the lock, reject if another interaction is pending; otherwise publish the
   clarification record.
3. Await asyncio.to_thread(answer_queue.get). This keeps the agent event loop
   responsive while Flask handles the answer.
4. Return the answer as a string and clear the record if it is still the same ID.

approve(request) follows the same steps and returns bool. Normalize only at the HTTP
boundary; the async method should return a real bool.

### F3. HTTP methods

GET /gateway/pending returns {"pending": null} or a JSON-safe pending object. It
must not expose the queue, lock, Python dataclass repr, or secrets.

POST /gateway/answer accepts the interaction id plus either answer for clarification
or approved for approval. Validate the current ID and kind under the lock, enqueue
exactly one result, and return 202. Unknown or stale IDs return 409. Invalid JSON
or invalid approval values return 400. Do not permit an answer to resolve a future
interaction.

The single pending invariant is intentional: OrbitAgent processes one action at a
time. A clear conflict response is safer than silently replacing a question with an
approval.

## G. Same-process run manager

The portal UI needs a way to start the agent without launching a second Python
process. A second process would have separate memory, so its events and gateway
responses would never reach this page.

Create a small manager in a Dev-3-owned module or app.py with:

~~~python
status: "idle" | "running" | "finished" | "failed"
run_id: str | None
goal: str | None
outcome: str | None
error: str | None
lock: threading.Lock
~~~

POST /run:

1. Parse a non-empty goal and optional real flag.
2. Under the lock, reject if status is running.
3. Select MockBrowserController for offline/default mode; select
   BrowserUseController for explicit real mode.
4. Construct OrbitAgent(browser, shared_gateway, shared_sink).
5. Start a daemon thread whose target calls asyncio.run(agent.run(goal)).
6. Return 202 with the run ID and status.

The thread must update finished/outcome or failed/error in a finally block. GET
/run/status returns a JSON-safe snapshot. Do not allow overlapping runs, because
the shared in-memory orders, gateway, and sink are single-demo resources.

Import the agent/browser classes lazily in the POST handler if needed. This keeps
the portal importable before Dev 1's real browser implementation is complete.
The product layer must not select a model, provider, or API key; those remain in
orbit.config and Dev 2's agent integration.

## H. Template and browser interaction contract

The template should contain these regions:

1. Orders: search, table, status, action buttons, and confirmation page.
2. Run/activity: goal input, Start button, run status, and scrolling event log.
3. Human decision: clarification text/options or approval summary with Approve and
   Reject buttons; hidden or disabled when no pending request exists.

Poll GET /gateway/pending approximately every 250 milliseconds, or use a small
backoff while idle. Send answers with fetch POST /gateway/answer and include the
pending ID. Disable buttons immediately after submit to avoid duplicate answers.

Start the run with fetch POST /run. Show 409 as an explanatory status instead of
silently resetting the UI. Use textContent for goal, event, question, and answer
strings. Do not insert model-generated strings via innerHTML.

The UI is a local demo; it does not need authentication or a database. It must
still tolerate a browser refresh: the activity history can be replayed from
recent(), and a pending request can be re-rendered from GET /gateway/pending.

## I. Dependencies and configuration

Required project dependencies are Python 3.11+, Flask 3+, pytest 8+, browser-use
for the real browser path, and python-dotenv. The product implementation should
prefer Python standard library queue, threading, asyncio, uuid, json, dataclasses,
and collections.deque. No additional dependency is necessary for SSE or polling.

The portal must render and pass offline tests without ANTHROPIC_API_KEY, Chrome,
Playwright, or network access. Read ORBIT_PORTAL_URL and ORBIT_HEADLESS through
orbit.config.settings only when needed. Never hard-code ANTHROPIC_API_KEY,
BROWSER_USE_API_KEY, a provider name, or model ID.

## J. Implementation order

1. Portal state machine: confirmation GET/POST, validation, semantic HTML, rename
   toggle, and one layout variation.
2. Activity transport: bounded history, per-client queues, SSE route, event panel,
   and generic event rendering.
3. Gateway: pending record, thread-safe answer handoff, pending/answer routes,
   clarification rendering, and approval rendering.
4. Run manager: shared sink/gateway instances, POST /run, status endpoint, mock
   run, then explicit real-browser option.
5. Tests and rehearsal: route tests, sink tests, gateway tests, run-manager tests,
   then the six demo beats in demo/demo_script.md.

Each step must be independently runnable. Use the mock browser until the UI
transport is working. Coordinate only at the protocol level with Dev 1 and Dev 2.

## K. Verification and tests

Portal tests should assert:

- GET / returns 200 and contains all five customers.
- q=john returns exactly the three Johns.
- POST /process/1 redirects to /confirm/1 and leaves order 1 pending.
- GET /confirm/1 shows customer/item/qty and Confirm & submit.
- POST /confirm/1 sets only order 1 to processed.
- invalid and already processed IDs are handled safely.
- RENAME_BUTTON changes visible Process to Fulfil without changing form action.

Activity tests should assert bounded history, event delivery to every active
subscriber, safe unsubscribe, correct SSE framing, and generic kind handling.

Gateway tests should start ask/approve asynchronously, inspect GET /gateway/pending,
resolve through POST /gateway/answer, verify the returned value, and reject stale
IDs. A second pending request must not overwrite the first.

Run-manager tests should assert 202 while idle, 409 while active, eventual terminal
status for a mock run, and identity of the shared sink/gateway used by routes.

Always run:

~~~text
pytest -q
python -m orbit.portal.app
~~~

No test may require Chrome, an API key, or network access. Existing
tests/test_loop_smoke.py must remain green.

## L. Integration checklist

Dev 1's semantic observation should see the search field, customer names, action
buttons, confirmation button, and status text. It should find Process and Fulfil
as the same meaning and survive the layout variation.

Dev 2's loop should be able to call WebGateway.ask for ActionType.ASK_USER,
WebGateway.approve before a RiskLevel.CONSEQUENTIAL action, and
WebActivitySink.emit for every existing event kind. A rejected approval must never
reach browser.execute.

No Dev-3 implementation should rely on private fields in Dev 1 or Dev 2. If a
new shared field is truly required, propose an additive contracts.py change first.

## M. Branch, commits, and delivery

Use a dedicated branch for this developer, preferably dev_3_product or the
repository's accepted feat/dev3-product equivalent. Keep commits small:

~~~text
docs(dev3): document independent product context
feat(portal): add confirmation workflow and semantic variation
feat(ui): stream activity events over SSE
feat(ui): add clarification and approval gateway
feat(portal): add same-process demo runner
test(dev3): cover portal and human-in-the-loop flows
~~~

Before pushing, inspect status, rebase on origin/main, run pytest -q, and push with
force-with-lease to the dedicated branch. Never push main. The final PR should
list routes, event payloads, gateway behavior, manual demo commands, and test
results so the other developers can integrate without reading implementation
internals.

## N. Final acceptance checklist

- Only orbit/portal, orbit/ui, Dev-3-owned tests, and this document changed.
- Orders/search/three-John ambiguity scenario are intact.
- Processing is pending → confirmation → processed.
- Rename and layout variations preserve semantic controls.
- SSE activity is live, bounded, and safe for multiple subscribers.
- Clarification/approval requests are correlated, blocking, and stale-safe.
- /run uses one in-process sink and gateway and rejects overlap.
- No key/model/provider is hard-coded.
- Offline tests pass and pytest -q is green.
- Changes are committed and pushed only to the dedicated Dev-3 branch.
