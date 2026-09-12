# orbit/browser — Dev 1 (Browser layer)

You are in **Dev 1's** layer. Full build playbook: `docs/DEV_1_BROWSER.md`.

**Job:** implement `BrowserUseController` in `session.py` — start/stop a real
Chrome, `observe()` the live page, `execute()` every `AgentAction` — on top of
browser-use.

Rules for this directory:
- Implement the `BrowserController` Protocol from `orbit/contracts.py` exactly.
- Target elements **semantically** (role / visible text / meaning), never fixed
  CSS selectors — this must survive a renamed button.
- This layer **executes and reports only**. It does not decide the next step and
  does not talk to the user.
- Keep `MockBrowserController` in sync with the contract; do not add features to it.
- browser-use's low-level API varies by version — confirm the real API for the
  pinned version first (`uv pip show browser-use`; docs.browser-use.com).
- Do **not** edit `orbit/agent/`, `orbit/portal/`, `orbit/ui/`.

Verify: `python -m orbit.main --real "open http://127.0.0.1:5000 and click Process on the first order"`
