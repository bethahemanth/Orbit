# Orbit — Browser Employee (Hackathon POC)

A browser-native AI agent that turns natural-language goals into executable
actions across websites, using **the browser itself as the integration layer**.

> *We do not integrate every website. We integrate with the browser itself.*
> The agent observes the live interface, reasons about what to do next, acts
> through Chrome, verifies the result, and asks the human whenever intent or
> authorization is unclear.

Built on [browser-use](https://github.com/browser-use/browser-use).

---

## Quickstart (runs offline in 30 seconds)

```bash
git clone https://github.com/bethahemanth/Orbit.git
cd Orbit

# Python >= 3.11
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"        # or: pip install -e ".[dev]"

python -m orbit.main "Process today's 5 orders"   # mock browser, no key needed
pytest -q                                          # smoke test, should pass
```

A fresh clone runs immediately: the loop is wired end-to-end with a mock browser
and console human, so every developer can build their part in isolation and swap
in the real pieces one at a time.

### Run the real thing

```bash
cp .env.example .env               # add the SHARED Anthropic key (see below)
uv run playwright install chromium
python -m orbit.portal.app         # terminal 1: the demo portal @ :5000
python -m orbit.main --real "Process today's 5 orders"   # terminal 2: real Chrome
```

## Built with Claude Code

This repo is set up for [Claude Code](https://docs.claude.com/en/docs/claude-code/overview).
Run `claude` in the repo root and it auto-loads `CLAUDE.md`; each layer also has a
nested `CLAUDE.md` that loads when you work in that directory, so Claude Code knows
your ownership boundary, the contract, and the semantic-targeting rule without being
told. Project slash commands live in `.claude/commands/`: `/verify`, `/sync`,
`/new-branch`, `/commit`, `/run-portal`. Each developer: open your
`docs/DEV_*.md` playbook and tell Claude Code to work the Build → Verify → Commit
steps in order.

## Shared Claude account

All three developers use **one** Anthropic account, so there is **one shared
`ANTHROPIC_API_KEY`** in `.env` (git-ignored — never commit it). A shared key means
**shared rate limits**: run against the mock while iterating, set `ORBIT_DEV_TAG`
to your name for traceable logs, and coordinate before heavy end-to-end runs. Each
`docs/DEV_*.md` has the details.

## Who builds what

| Developer | Owns | Guide |
|---|---|---|
| **Dev 1 — Browser** | `orbit/browser/` — Browser Use session, execution, page perception | [docs/DEV_1_BROWSER.md](docs/DEV_1_BROWSER.md) |
| **Dev 2 — Agent** | `orbit/agent/`, `orbit/control/` — the loop, clarification, verification, recovery | [docs/DEV_2_AGENT.md](docs/DEV_2_AGENT.md) |
| **Dev 3 — Product** | `orbit/portal/`, `orbit/ui/` — portal, activity UI, approval flow, demo | [docs/DEV_3_PRODUCT.md](docs/DEV_3_PRODUCT.md) |

The three layers meet only at the shared seam, **`orbit/contracts.py`**. Everyone
codes against those Protocols, so work happens in parallel with almost no conflicts.

## Layout

```
orbit/
  contracts.py     # SHARED seam: AgentAction, Observation, BrowserController, HumanGateway, ActivitySink
  config.py        # settings + the shared Claude key
  main.py          # wires the three layers together (mocks by default, --real to go live)
  browser/         # Dev 1
  agent/           # Dev 2
  control/         # Dev 2 (console human/activity defaults; Dev 3's UI replaces them)
  portal/          # Dev 3 — the demo business portal (Flask)
  ui/              # Dev 3 — live activity + approval UI
docs/
  ARCHITECTURE.md  # the design, mapped to code
  GIT_WORKFLOW.md  # branching, naming, rebase/merge, conflicts  ← read this
  DEV_1_BROWSER.md / DEV_2_AGENT.md / DEV_3_PRODUCT.md
demo/
  demo_script.md   # the 90-second run of show
tests/
```

## Git in one breath

`main` stays runnable. Work on `feat/devN-short-desc` branches, commit small,
**rebase onto `main`** (don't merge it in), `push --force-with-lease`, open a PR.
Full rules — naming, rebase vs. merge, conflict resolution, the shared-file
protocol — are in **[docs/GIT_WORKFLOW.md](docs/GIT_WORKFLOW.md)**.

## Definition of done

A natural-language goal drives a browser task with no site-specific script; the
agent recovers when the page changes; ambiguity produces a question; consequential
actions pause for approval; one business portal **and** one real website work with
the same core agent. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
