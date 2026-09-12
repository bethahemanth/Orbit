# QA Fixes — Offline Loop & Windows Console Robustness

## Branch: `feat/qa-fixes-offline-loop`

## Summary

This document records the bugs discovered during the full QA and end-to-end
debugging audit of the Orbit agentic AI browser project, their root causes,
and the minimal fixes applied to return the project to a reliably runnable
state. No features were added. All existing functionality is preserved.

---

## Bugs Found & Fixed

### Fix 1 — `MockBrowserController`: Static State Caused Infinite Verification Failures

**Affected File:** `orbit/browser/session.py`

**Symptoms:**
- `pytest` reported: `OSError: pytest: reading from stdin while output is
  captured!` in `tests/test_loop_smoke.py::test_loop_runs_offline`.
- `python -m orbit.main "Process today's 5 orders"` hung at the console
  asking for user input after the agent entered recovery mode.

**Root Cause:**
`MockBrowserController.observe()` returned an identical `page_summary` and
`interactive_elements` on every call regardless of how many `CLICK` actions
had been executed. When Dev 2 introduced `OrbitAgent.verify()`, the loop
compared pre- and post-action observations for every `CLICK`: since nothing
in the mock changed, `verify()` returned `False` on every step. After
`_MAX_CONSECUTIVE_FAILURES = 3` consecutive failures, the loop called
`ConsoleGateway.ask()` which invoked `input()` — hanging or crashing in
non-interactive environments (pytest, CI, background subprocesses).

**Fix Applied:**
Added stateful order tracking to `MockBrowserController`. `_orders_left`
starts at 5 and decrements on every `CLICK`. Once it reaches 0, `observe()`
removes the `'Process' button` element from `interactive_elements`, causing
`RulePlanner._first_actionable()` to return `None` and the loop to emit
`ActionType.FINISH`. `verify()` now returns `True` on every step because
`page_summary` changes after each click (5 rows → 4 rows → ... → 0 rows).

**Result:**
- `pytest -q` → 83 passed (was 1 failed)
- `python -m orbit.main` → reaches `outcome: done` in 5 steps without hanging

---

### Fix 2 — `ConsoleGateway`: Unguarded `input()` Crashes in Non-Interactive Environments

**Affected File:** `orbit/control/human.py`

**Symptoms:**
- `OSError: pytest: reading from stdin while output is captured!` during the
  smoke test whenever recovery clarification was triggered.
- `EOFError` in CI pipelines and background task runners without a tty.

**Root Cause:**
`ConsoleGateway.ask()` and `ConsoleGateway.approve()` called `input()` with
no exception handling. When pytest's output capture intercepted stdin, or
when the process ran without a connected terminal, `input()` raised `OSError`
or `EOFError`.

**Fix Applied:**
Wrapped both `input()` calls in `try...except (EOFError, OSError)`:
- `ask()` returns `request.options[0]` (first option) or `""` if stdin fails.
- `approve()` returns `False` (safe default: reject consequential action).

Interactive terminal usage is completely unaffected — in that mode `input()`
succeeds normally and the except block is never reached.

---

### Fix 3 — `ConsoleActivitySink`: `UnicodeEncodeError` on Windows Console

**Affected File:** `orbit/control/human.py`

**Symptoms:**
- `UnicodeEncodeError: 'charmap' codec can't encode character '\u25b6' in
  position 1576: character maps to <undefined>` when printing DOM tree
  summaries from real browser sessions on Windows.
- Crash in `ConsoleActivitySink.emit()` when `BrowserUseController` reported
  a page containing Unicode navigation arrows or emoji from the accessibility
  tree.

**Root Cause:**
Windows `cmd.exe` / PowerShell default to the `cp1252` code page for stdout.
`browser-use 0.13.x` includes Unicode symbols (▶ `\u25b6`, emoji) in its DOM
representation strings. `cp1252` cannot encode these characters, so `print()`
raises `UnicodeEncodeError`.

**Fix Applied:**
Wrapped `print()` in `ConsoleActivitySink.emit()` with
`try...except UnicodeEncodeError` that falls back to ASCII with replacement
characters (`errors="replace"`). On terminals with full Unicode support
(UTF-8 on Linux/macOS) the fast path is always taken and the fallback is
never reached.

---

## Verification Results

| Check | Result |
|-------|--------|
| `pytest -q` — 83 tests | ✅ 83 passed in 3.81s |
| `python -m orbit.main "Process today's 5 orders"` | ✅ outcome: done (5 steps) |
| Phase 3 — Minimal Browser Test (real Chromium headless) | ✅ |
| Phase 4A — Open webpage and extract title | ✅ |
| Phase 4B — Search DuckDuckGo for "OpenAI" | ✅ |
| Phase 4C — Click link, observe URL change | ✅ |
| Phase 4D — Fill and submit local portal search form | ✅ |
| Phase 4E — Multi-page navigation and data extraction | ✅ |
| Phase 5 — Failure & Recovery (6 scenarios) | ✅ all graceful |
| Phase 6 — Real-world Wikipedia DOM navigation | ✅ |
| Phase 7 — 5 consecutive reliability runs | ✅ 5/5, avg 7.80s |
| Phase 9 — Full E2E: real Chromium → local portal → 5 orders confirmed | ✅ outcome: done |

---

## Files Changed

| File | Change |
|------|--------|
| `orbit/browser/session.py` | `MockBrowserController`: stateful `_orders_left` counter, dynamic `observe()`, decrement on `CLICK` |
| `orbit/control/human.py` | `ConsoleGateway.ask()` + `approve()`: `EOFError`/`OSError` guard; `ConsoleActivitySink.emit()`: `UnicodeEncodeError` guard with ASCII fallback |
| `docs/QA_FIXES.md` | This document |

## No Breaking Changes

- All 83 existing tests remain green.
- `BrowserUseController` (real browser), `OrbitAgent`, `LLMPlanner`,
  `RulePlanner`, `contracts.py`, `config.py`, `main.py`, `orbit/portal/`,
  and `orbit/ui/` are untouched.
- Offline mode still requires zero API keys and zero external services.
