---
description: Create a correctly-named feature branch off the latest main
argument-hint: [dev1|dev2|dev3] [short-description]
allowed-tools: Bash(git:*)
---
Create a branch following Orbit's convention `<type>/<dev>-<short-description>`:
1. `git checkout main && git pull --rebase origin main`
2. `git checkout -b feat/$1-$2` (kebab-case the description in $2).
Then confirm the new branch name back to me.
