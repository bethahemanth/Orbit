# 90-Second Demo Script

The run of show. Rehearse it so the final take is clean (spec §10).

1. **"Process today's five orders."**
   Agent reads the task, opens the portal, discovers the form, and processes the
   first order.

2. **Show live activity.**
   observe → action → result → verification appears in the UI activity panel.

3. **Change the portal label/layout.**
   Flip `RENAME_BUTTON` (Process → Fulfil) in `orbit/portal/app.py`, run another
   order — the agent finds the semantically correct control instead of relying on
   a fixed selector.

4. **Give an ambiguous command.**
   "Process John's order." Three Johns exist → the agent asks *which* John instead
   of guessing.

5. **Switch to a real website.**
   "Check my latest order." The same browser-agent stack drives an unrelated,
   real site — proving it isn't a portal-specific bot.

6. **Explain the value.**
   "The browser is our integration layer; every website does not need its own API
   connector."

---

**Positioning line to close on:**
*"Any web interface can become a tool when an agent can see it, reason about it,
act on it, and verify the result."*
