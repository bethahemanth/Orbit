---
description: Sync my branch with the latest main via rebase
allowed-tools: Bash(git:*), Bash(pytest:*)
---
Bring my branch up to date safely:
1. `git fetch origin`
2. `git rebase origin/main`
3. If there are conflicts: show them. If a conflict is in a directory I do NOT own, stop and warn me. Otherwise help resolve, then `git rebase --continue`.
4. Run `pytest -q` to confirm it's still green.
Never use plain `git push --force`; if a push is needed, use `--force-with-lease`.
