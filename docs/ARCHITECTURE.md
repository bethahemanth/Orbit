# Orbit — Architecture

> **Thesis:** *We do not integrate every website. We integrate with the browser itself.*
> The agent observes the live interface, reasons about what to do next, acts through
> Chrome, verifies the result, and asks the human whenever intent or authorization is unclear.

Orbit is the hackathon POC of a **Browser Employee**: a browser-native AI agent that
turns a natural-language goal into executable actions across any website, using the
browser as the universal integration layer.

## The core loop

```
GOAL → OBSERVE → REASON → ACT → OBSERVE → VERIFY → CONTINUE / RECOVER → COMPLETE
```

Key principle: **do not** hard-code `Amazon → Orders → Track` or `Portal → button #7`.
Encode reusable browser capabilities and let the agent infer the live workflow from
the page state.

## Layers → code

| Layer | Responsibility | Where it lives | Owner |
|---|---|---|---|
| 1. User / Goal | Natural-language request | `orbit/main.py` (CLI) / portal input | Dev 3 |
| 2. Task / Control | Intent check, clarification, approval, task state | `orbit/agent/`, `orbit/control/` | Dev 2 (+ Dev 3 UI) |
| 3. Browser Use Agent | Planning & action selection | `orbit/agent/loop.py` | Dev 2 |
| 4. Live Page Perception | DOM / accessibility / screenshot | `orbit/browser/session.py` | Dev 1 |
| 5. Chrome / Playwright | navigate, click, type, select, scroll | `orbit/browser/session.py` | Dev 1 |
| 6. Websites | business portal + one real site | `orbit/portal/` | Dev 3 |
| 7. Result / Recovery | verify, recover, continue, complete | `orbit/agent/loop.py` | Dev 2 |

## The seam: `orbit/contracts.py`

Everyone codes against the Protocols and dataclasses in `orbit/contracts.py`:

- **`BrowserController`** — Dev 1 implements (`BrowserUseController`). A `MockBrowserController` ships so others can run without a browser.
- **`HumanGateway`** — Dev 3 implements in the web UI (`WebGateway`). A `ConsoleGateway` ships as the default.
- **`ActivitySink`** — Dev 3 implements (`WebActivitySink`). A `ConsoleActivitySink` ships as the default.
- **`AgentAction` / `Observation` / `ActionResult`** — the data that flows between them.

Because the seam is stable, all three people build and test **in parallel** against
mocks, then swap in real implementations one at a time in `orbit/main.py`. Nothing
else has to change.

## Minimal action contract (spec §6)

```
AgentAction = navigate | click | type | select | scroll | back | ask_user | finish
```

`target` is **semantic** (role / visible text / meaning), never a hard-coded CSS
selector. Consequential actions (submit / purchase / delete / send) are marked
`RiskLevel.CONSEQUENTIAL` and routed through human approval.

## Definition of done (spec §12)

- A natural-language goal drives a browser task with no site-specific script.
- The agent observes a live page, picks a generic action, and continues after the page changes.
- Ambiguity produces a clarification question, not a guess.
- Consequential actions pause for explicit approval.
- One business workflow **and** one unrelated real website work with the same core agent.
- The demo shows why *browser automation* — not an API integration — is the enabler.
