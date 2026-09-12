# orbit/ui — Dev 3 (activity + approval UI)

You are in **Dev 3's** layer. Full build playbook: `docs/DEV_3_PRODUCT.md`.

**Job:** implement `WebActivitySink` (live observe→action→result→verify feed) and
`WebGateway` (ask + Approve|Reject), both from `orbit/contracts.py`. They drop into
the agent in place of the `Console*` defaults.

Important: for the web path to work, the agent must run in the **same process** as
Flask (they share an in-memory queue). Add a `POST /run` endpoint that starts the
agent in a background task rather than running `orbit.main` separately. See the
playbook. Do **not** edit `orbit/browser/`, `orbit/agent/`.
