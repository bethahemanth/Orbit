# orbit/agent — Dev 2 (Agent layer)

You are in **Dev 2's** layer. Full build playbook: `docs/DEV_2_AGENT.md`.

**Job:** implement `decide()` and `verify()` in `loop.py` — the
OBSERVE → REASON → ACT → VERIFY → RECOVER brain of `OrbitAgent`.

Rules for this directory:
- Reason via the shared Claude account (`orbit.config.settings.model`). Keep
  `max_steps` low while iterating — the account's rate limits are shared.
- Build and test against `MockBrowserController` + `ConsoleGateway` first; you do
  not need Dev 1 or Dev 3 finished.
- Emit `ActionType.ASK_USER` for ambiguity; mark submit/purchase/delete/send as
  `RiskLevel.CONSEQUENTIAL` — the loop routes those to approval automatically.
- Targets are **semantic descriptions**; Dev 1 resolves them to elements.
- You own the final wiring in `orbit/main.py` — do it **last** and announce it
  (shared file).
- Do **not** edit `orbit/browser/`, `orbit/portal/`, `orbit/ui/`.

Verify: `python -m orbit.main "Process John's order"` should ask *which* John.
