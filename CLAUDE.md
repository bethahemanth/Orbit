# CLAUDE.md — Orbit

Orbit is a browser-native AI agent (hackathon POC): a natural-language goal becomes
browser actions, using **the browser itself as the integration layer**. Built on
[browser-use](https://github.com/browser-use/browser-use).

Claude Code loads this file automatically every session. Nested `CLAUDE.md` files
in each layer load on demand when you touch that layer's files.

## How this repo is built

Three developers, three layers, one shared seam. The step-by-step build playbooks
are the source of truth:

- `docs/DEV_1_BROWSER.md` — Browser layer (`orbit/browser/`)
- `docs/DEV_2_AGENT.md` — Agent layer (`orbit/agent/`, `orbit/control/`)
- `docs/DEV_3_PRODUCT.md` — Product/Demo layer (`orbit/portal/`, `orbit/ui/`)
- `docs/ARCHITECTURE.md` — the design mapped to code
- `docs/GIT_WORKFLOW.md` — branching, naming, rebase/merge, conflicts

**When helping a developer:** read their `docs/DEV_*.md` playbook and the nearest
`CLAUDE.md`, then work the **Build → Verify → Commit** steps in order. Run the
Verify command after each step; don't move on until it's green.

## Golden rules (do not violate)

1. **Edit only your layer's directory.** Ownership:
   `orbit/browser/` → Dev 1 · `orbit/agent/` + `orbit/control/` → Dev 2 ·
   `orbit/portal/` + `orbit/ui/` → Dev 3.
2. **`orbit/contracts.py` is the shared seam.** Changing it breaks the others.
   Additive changes only, announce first, land as a tiny `chore(contracts)` PR.
3. **Target elements semantically** (role / visible text / meaning), never
   hard-coded CSS selectors. That is the whole thesis.
4. **Keep `pytest -q` green** before every commit.
5. **Never push to `main`.** Work on a branch; rebase onto `main`, never merge
   `main` into your branch; push with `--force-with-lease`.

## Run & verify

```bash
python -m orbit.main "Process today's 5 orders"   # offline, no key needed
pytest -q                                          # smoke test
python -m orbit.portal.app                         # demo portal @ :5000
python -m orbit.main --real "..."                  # real Chrome (needs .env + playwright)
```

## Shared Claude account

All three developers use **one** Anthropic account. That means **shared rate
limits — for Claude Code itself and for the agent's LLM.** Coordinate heavy runs,
keep agent `max_steps` low while iterating, and set `ORBIT_DEV_TAG` to your name.
**Never commit `.env`.**

## Project slash commands (`.claude/commands/`)

`/verify` · `/sync` · `/new-branch <dev> <desc>` · `/commit <type(area): msg>` · `/run-portal`
