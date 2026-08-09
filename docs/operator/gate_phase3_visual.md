# Phase 3 visual gate — the 10-minute browser check

Run AFTER `gate_phase3_auto.py` prints `VERDICT: PASS`.

1. Start the platform: `docker compose up -d`
2. Open http://localhost:5173 and click the **AI Council** tab.
3. Click **Load demo session (synthetic, $0)**.
4. Check, with your own eyes:
   - [ ] The session appears in the list, labeled **synthetic**, status
         **completed**.
   - [ ] The **cost panel** shows a bar under the $5 session cap, a per-role
         and per-provider breakdown, and a cache-savings line.
   - [ ] The **Arbiter decision** card shows a confidence number and a
         rationale.
   - [ ] The **Design specs** section shows 3 specs, each marked
         **schema-valid** with a hash.
   - [ ] The **Transcript** shows 16 calls; opening any call card shows the
         full prompt and full response text.
5. If you have run a live session: open it from the list. It must NOT be
   labeled synthetic, and every call card shows real token counts and costs.
   If the session is marked **degraded**, find the call card with the red
   error badge — the error text names the provider and reason.

If every box checks: Phase 3 gate is PASSED. Note the date in your records.
