---
description: Run Orbit's smoke test and offline agent run
allowed-tools: Bash(pytest:*), Bash(python:*)
---
Verify the project is healthy:
1. Run `pytest -q` and report pass/fail.
2. Run `python -m orbit.main "Process today's 5 orders"` and confirm the loop completes.
If anything fails, diagnose and propose the smallest fix — and only edit files in my layer's directory.
