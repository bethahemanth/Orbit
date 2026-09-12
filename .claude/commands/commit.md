---
description: Stage and commit using Orbit's Conventional Commits format
argument-hint: [type(area): message]
allowed-tools: Bash(git:*), Bash(pytest:*)
---
1. Run `pytest -q`. If it fails, STOP and tell me — never commit red.
2. Show `git status` and `git diff --stat`.
3. Stage changes in MY layer's directory only.
4. Commit with a Conventional-Commits message from: $ARGUMENTS
   (e.g. `feat(browser): implement execute() for click/type/navigate`).
