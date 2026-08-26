---
description: Weekly — regenerate the Hub status and find where the docs have drifted from the repo
---

Weekly drift check. Nothing here changes behaviour; it finds lies before they
become load-bearing.

1. **Regenerate the Hub status.** Give the operator the PowerShell command to
   run themselves (their machine, their path):
   ```powershell
   python scripts\generate_hub_status.py --out "E:\Burook platform development\Luxurycon\AI-Team-Hub\luxuryform_status.json"
   ```

2. **Audit `LIMITATIONS.md` against the actual repo state.** For every entry,
   check the code and say whether it is: still true, now false (and what closed
   it, with the evidence), or partly true (and which half). Never renumber a
   section — retired entries keep their number so old references stay valid.

3. **Audit `NEXT.md` against `git log`.** Anything shipped that is not ticked,
   or ticked that is not shipped, is a finding.

4. **Cross-check the documents against each other.** `CLAUDE.md`, `README.md`,
   the phase reports and the plans all state the build status. Where two
   disagree, quote both and say which one the code supports.

5. **Check the pins are still pins.** `config/pricing.yaml` `pricing_version`,
   the Docker image and package pins (`tests/test_docker_pins.py`), the
   frontend lockfile. A pin that has quietly moved is a determinism failure
   waiting to be discovered at the worst moment.

6. **Check `data/geo_scratch/`** — it is never reaped, one directory per sandbox
   job forever. Report its size so it stays visible while it is still harmless.

Report findings only. Fix nothing in this command; each fix is its own commit
with its own reason.
