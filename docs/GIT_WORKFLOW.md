# Git Workflow — read this once, then keep it open

Three people, one repo, three hours. This workflow keeps you out of each other's
way. It is intentionally simple. Each `DEV_*.md` repeats the essentials, but this
is the full reference.

## 0. The golden rule of parallel work

**You own your directory. You do not edit someone else's directory.**

| You are | You edit | You do NOT edit |
|---|---|---|
| Dev 1 (Browser) | `orbit/browser/` | `orbit/agent/`, `orbit/portal/`, `orbit/ui/` |
| Dev 2 (Agent) | `orbit/agent/`, `orbit/control/` | `orbit/browser/`, `orbit/portal/`, `orbit/ui/` |
| Dev 3 (Product) | `orbit/portal/`, `orbit/ui/` | `orbit/browser/`, `orbit/agent/` |

`orbit/contracts.py`, `orbit/main.py`, `orbit/config.py` are **shared**. Touching
them needs a heads-up in the group chat first (see §6). This single rule prevents
~90% of merge conflicts.

## 1. Branches

`main` is always runnable. Nobody pushes to `main` directly. You work on your own
branch and open a Pull Request.

### Naming convention

```
<type>/<dev>-<short-description>
```

- `<type>` — one of `feat`, `fix`, `chore`, `docs`, `demo`.
- `<dev>` — `dev1`, `dev2`, or `dev3` (so anyone can see whose branch it is at a glance).
- `<short-description>` — 2–4 words, kebab-case.

Examples:
```
feat/dev1-browser-execute
feat/dev2-clarification-loop
feat/dev3-order-portal
fix/dev2-verify-recovery
docs/dev3-demo-script
```

Create yours off the latest `main`:
```bash
git checkout main
git pull origin main
git checkout -b feat/dev1-browser-execute
```

## 2. Commits

Small and frequent beats one giant commit. Format:

```
<type>(<area>): <what changed>
```

Examples:
```
feat(browser): implement execute() for click/type/navigate
feat(agent): add consequential-action approval gate
fix(portal): rename Process button for the UI-variation demo
```

Commit whenever a piece works. In a hackathon, `git commit` is your undo button.

## 3. Push and open a PR

```bash
git push -u origin feat/dev1-browser-execute
```

Open a PR into `main` on GitHub. Keep PRs small. One teammate skims it and clicks
merge — in a 3-hour sprint, review is a 60-second sanity check, not a gate.

## 4. Keep your branch fresh — **rebase**, don't merge `main` into your branch

Before you push, and any time `main` moves, replay your work on top of the latest
`main`. This keeps history linear and avoids noisy "Merge branch 'main'" commits.

```bash
git fetch origin
git rebase origin/main
# ...resolve any conflicts (see §5), then:
git push --force-with-lease
```

- Use `--force-with-lease`, **never** plain `--force` — it refuses to clobber a push
  a teammate made to your branch while you weren't looking.
- Only rebase branches that are yours. Never rebase `main`.

### Rebase vs. merge — which, when

| Situation | Do this |
|---|---|
| Updating **your feature branch** with the latest `main` | `git rebase origin/main` |
| Landing your finished feature **into `main`** | open a PR, use **Squash and merge** on GitHub |
| Pulling `main` at the start of the day | `git pull --rebase origin main` |

Set rebase-on-pull once so you never merge by accident:
```bash
git config --global pull.rebase true
```

## 5. Resolving conflicts (stay calm — it's routine)

A conflict just means two branches changed nearby lines. Git pauses and marks them:

```
<<<<<<< HEAD           (what's already on main)
label = "Fulfil"
=======                (your change)
label = "Process"
>>>>>>> feat/dev3-...
```

1. Open each file Git lists, delete the `<<<<<<<`, `=======`, `>>>>>>>` markers,
   and keep the correct combined result.
2. If the conflict is in **someone else's directory**, stop and ping them — you
   probably shouldn't be editing it (see §0).
3. Mark resolved and continue:
   ```bash
   git add <file>
   git rebase --continue
   ```
4. Lost or confused? Abort and you're back where you started:
   ```bash
   git rebase --abort
   ```
5. Run the smoke test before continuing: `pytest -q` must pass.

## 6. Changing a shared file (`contracts.py`, `main.py`, `config.py`)

The contract is the seam the other two are coding against. If you change it under
them, their code breaks.

1. Announce it in the group chat: *"I need to add a field to `AgentAction`."*
2. Prefer **additive** changes (new optional field) over renames/removals.
3. Make it a tiny, standalone PR (`chore(contracts): ...`) and get it into `main` fast.
4. Everyone else runs `git pull --rebase origin main` right after it lands.

## 7. End-of-integration merge order

When wiring the real pieces together near the demo, land in this order to minimise
churn (each depends on the one before it being on `main`):

1. **Dev 1** — real `BrowserController`.
2. **Dev 3** — portal + `WebGateway`/`WebActivitySink`.
3. **Dev 2** — flip `orbit/main.py` to use the real controller + web UI, verify the loop.

Then everyone rebases on `main` and the final demo runs from `main`.

## 8. Quick reference

```bash
git checkout main && git pull --rebase origin main   # start fresh
git checkout -b feat/dev2-clarification-loop         # your branch
# ...work, commit small...
git fetch origin && git rebase origin/main           # stay current
git push --force-with-lease                          # update your PR
pytest -q                                            # keep it green
```
