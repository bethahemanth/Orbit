# Dev 1 — Build the Browser Layer

**Your mission: make `orbit/browser/session.py` drive a real Chrome.** When you're
done, the agent can say "click the Process button" and it happens in a live
browser, and `observe()` tells the agent what the page looks like now.

You build **`BrowserUseController`**. Nothing else. You edit **only
`orbit/browser/`**.

---

## Build this with Claude Code

From the repo root, launch Claude Code:

```bash
claude
```

- The root `CLAUDE.md` plus the nested `orbit/browser/CLAUDE.md` load
  automatically as you work — Claude Code already knows your layer, your
  constraints, and the contract.
- Point it at this playbook and let it work step by step:
  > "Read docs/DEV_1_BROWSER.md and do Build step 1. After each step, run /verify and /commit."
- Project slash commands: `/verify`, `/new-branch dev1 browser-execute`, `/commit`,
  `/sync`, `/run-portal`.
- **Shared Claude account:** all three of you are on one account, so Claude Code
  usage limits are shared too. Coordinate long sessions; if you hit a limit, pause
  and let it recover.

## Setup (5 min)

```bash
git clone https://github.com/bethahemanth/Orbit.git && cd Orbit
git checkout main && git pull --rebase origin main
uv venv && source .venv/bin/activate         # Python >= 3.11
uv pip install -e ".[dev]"
uv run playwright install chromium
cp .env.example .env                          # paste the SHARED ANTHROPIC_API_KEY, set ORBIT_DEV_TAG=dev1
python -m orbit.main "Process today's 5 orders"   # proves the clone runs (mock)
```

**Shared Claude account:** one key for all three of you = shared rate limits. Your
layer barely needs the model, so test against the mock and only hit the real model
in the joint end-to-end run. Use the account to *write code* freely (see the
prompts below) — that doesn't touch the agent's API quota.

**First, pin the version and learn the API you actually have:**
```bash
uv pip show browser-use          # note the version, tell the team to pin it
python -c "import browser_use, inspect; print(dir(browser_use))"
```
> browser-use's low-level API differs across versions. Confirm the real class and
> method names for *your* installed version before copying any snippet below.
> Fast way: paste the `dir(browser_use)` output into your Claude account and ask
> "how do I open a page, click by visible text, and read the DOM in this version?"

---

## Build step 1 — start/stop a real browser (target: 0:00–0:20)

**Build.** In `orbit/browser/session.py`, implement `start()` and `stop()`:

```python
from browser_use import Browser          # confirm this import for your version

class BrowserUseController(BrowserController):
    def __init__(self, headless: bool = False) -> None:
        self.headless = headless
        self._browser = None

    async def start(self) -> None:
        self._browser = Browser(headless=self.headless)
        await self._browser.start()

    async def stop(self) -> None:
        if self._browser:
            await self._browser.stop()
```

**Verify.**
```bash
python -c "import asyncio; from orbit.browser import BrowserUseController; \
c=BrowserUseController(); asyncio.run(c.start()); print('chrome up'); asyncio.run(c.stop())"
```
Chrome should open and close.

**Commit.** `git commit -am "feat(browser): start/stop real chrome session"`

**Claude prompt if stuck:** *"In browser-use vX.Y, give me the minimal async code to launch and cleanly close a Chromium session. Here's `dir(browser_use)`: …"*

---

## Build step 2 — `observe()` returns the live page (target: 0:20–0:45)

**Build.** Fill `observe()` to return an `Observation` (url, title, a text summary
the LLM can reason over, and the list of interactive elements). Use the DOM /
accessibility state browser-use exposes; add a screenshot when easy.

```python
async def observe(self) -> Observation:
    page = self._browser.get_current_page()      # confirm accessor for your version
    return Observation(
        url=page.url,
        title=await page.title(),
        page_summary=await self._summarize(page),        # text of the visible page
        interactive_elements=await self._list_elements(page),  # buttons/links/inputs by role+text
        screenshot_path=await self._screenshot(page),    # optional
    )
```

Write the small helpers so the summary and element list are **semantic** (role +
visible text), e.g. `"button: 'Process order'"`, `"input: 'Search customer'"`.

**Verify.** Point it at the demo portal (ask Dev 3 to run `python -m orbit.portal.app`):
```bash
python -c "import asyncio; from orbit.browser import BrowserUseController; from orbit.contracts import AgentAction, ActionType; \
c=BrowserUseController(); \
async def go():\n    await c.start(); await c.execute(AgentAction(type=ActionType.NAVIGATE, target='http://127.0.0.1:5000')); \
    print((await c.observe()).interactive_elements); await c.stop()\nasyncio.run(go())"
```
You should see the Process buttons / search field listed.

**Commit.** `feat(browser): observe() returns live page state`

---

## Build step 3 — `execute()` for every action type (target: 0:45–1:30)

**Build.** Map each `ActionType` onto a browser capability. **Target by meaning,
never a fixed CSS selector** — this is the whole thesis and what survives a
renamed button.

```python
async def execute(self, action: AgentAction) -> ActionResult:
    try:
        t = action.type
        if t == ActionType.NAVIGATE: await self._goto(action.target)
        elif t == ActionType.CLICK:  await self._click_semantic(action.target)   # find by role+text
        elif t == ActionType.TYPE:   await self._type_semantic(action.target, action.value)
        elif t == ActionType.SELECT: await self._select_semantic(action.target, action.value)
        elif t == ActionType.SCROLL: await self._scroll(action.value)
        elif t == ActionType.BACK:   await self._back()
        else: return ActionResult(False, f"unhandled {t}")
        return ActionResult(True, f"did {t.value} on {action.target!r}", await self.observe())
    except Exception as e:
        return ActionResult(False, "action failed", error=str(e))
```

The important helper is `_click_semantic(target)`: resolve the element from the
target *description* — prefer role+accessible-name matching, fall back to visible
text, then fuzzy match. That's what makes "the Process button" still work after
it's renamed to "Fulfil".

**Verify.** Click order 1 on the portal end-to-end:
```bash
python -m orbit.main --real "open http://127.0.0.1:5000 and click Process on the first order"
```
The row's status should flip to `processed`.

**Commit.** `feat(browser): execute() for navigate/click/type/select/scroll/back`

**Claude prompt:** *"Write `_click_semantic(description)` for browser-use vX that
finds an element by ARIA role + accessible name, then by visible text, then fuzzy,
and clicks it. Return a clear error if nothing matches."*

---

## Build step 4 — robustness + second website (target: 1:30–3:00)

- Add small waits / retries so actions don't race the page.
- Test on a **real** site (e.g. an order-lookup page) to prove you're not a
  portal-specific bot — same controller, no code changes.
- For logged-in sites, reuse a real Chrome profile (browser-use `real_browser.py`
  example) so sessions persist.

**Verify (your definition of done):**
- `--real` run processes an order on the portal.
- Dev 3 flips the button label Process→Fulfil; your `execute()` still finds it.
- The same controller drives one unrelated real website.

---

## Git — the short version (full rules: `docs/GIT_WORKFLOW.md`)

```bash
git checkout -b feat/dev1-browser-execute       # branch name: <type>/dev1-<what>
# ...small commits per step above...
git fetch origin && git rebase origin/main      # rebase onto main, never merge it in
git push --force-with-lease                      # open a PR into main
```
Edit **only `orbit/browser/`**. Need a change in `orbit/contracts.py`? It's the
shared seam — announce it in chat, keep it additive, land a tiny `chore(contracts)`
PR. Keep `pytest -q` green.
