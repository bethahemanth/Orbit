# orbit/portal — Dev 3 (business portal)

You are in **Dev 3's** layer. Full build playbook: `docs/DEV_3_PRODUCT.md`.

**Job:** a generic Flask orders portal the agent discovers and operates.

Rules for this directory:
- Keep it **generic** — the agent must discover the workflow, not be hard-wired.
- Add a confirm step (a genuinely consequential action for the approval demo).
- Wire the `RENAME_BUTTON` toggle (Process→Fulfil) + one field-move variation for
  the semantic-recovery demo. Keep the three "John" customers (ambiguity demo).
- Do **not** edit `orbit/browser/`, `orbit/agent/`.

Verify: `python -m orbit.portal.app`, then click Process and watch a row flip.
