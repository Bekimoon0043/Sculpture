# hub/ — one-way status sync: this repo → the LuxuryCon AI Command Hub

Nothing in this directory is part of the LuxuryForm platform. It is sync
tooling only: it reads the repo and produces a status payload the Hub can
display. **The Hub never writes back.** The panel issues `GET` requests and
nothing else; the generator opens the SQLite database with a `mode=ro` URI, so
it physically cannot mutate platform data.

## Files

| File | What it is |
|---|---|
| `../scripts/generate_hub_status.py` | The generator. Derives everything; hand-maintains nothing. |
| `luxuryform_status_panel.html` | The Hub-side panel. Standalone page **and** paste-in snippet. |
| `luxuryform_status.json` | Generated output. Gitignored — it is derived, never source. |

## Regenerate the status

```
python scripts/generate_hub_status.py
```

Writes `hub/luxuryform_status.json`. To write straight into the directory that
holds your Hub HTML instead:

```
python scripts/generate_hub_status.py --out /path/to/hub/luxuryform_status.json
```

The database is not in the repo (`data/` is gitignored), so point at it when
you want real spend numbers:

```
python scripts/generate_hub_status.py --db ./data/luxuryform.db
```

Otherwise every spend field is written as `null` with the reason recorded in
the payload's `undetermined` array.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Status file written; every field determined. |
| `2` | Status file written and valid; some fields are `null` (each listed in `undetermined`). |
| `1` | Fatal — no status file was written. |

`2` is a normal outcome, not a failure: with no database present, or with a
phase that has no gate verdict yet, the honest answer is `null`.

## Wire it into the Hub

1. Copy everything between `<!-- BEGIN PASTE -->` and `<!-- END PASTE -->` in
   `luxuryform_status_panel.html` into your Hub HTML.
2. Put `luxuryform_status.json` in the same directory as the Hub file, so the
   panel fetches it same-origin and no CORS configuration is needed.
3. Adjust the `data-` attributes on the `#lf-status` div if needed:
   `data-status-url`, `data-poll-seconds`, `data-stale-minutes`.

Opening `luxuryform_status_panel.html` directly over `http://` also works as a
preview — it is a complete page on its own. (Open it over `http://`, not
`file://`; browsers block `fetch` of local files from a `file://` page.)

## Reading the panel

The **commit sha** is the headline, in large monospace type. It is the answer
to "is what I'm looking at current?" — compare it against `git log -1` in the
repo. Around it:

- `tree clean` / `tree dirty (n)` — whether the generator ran against
  uncommitted work.
- A **stale** banner once the payload passes `data-stale-minutes` (default 20).
- A **fetch failed** banner if polling breaks. The panel keeps showing the last
  payload it loaded but marks it frozen, so a dead poller can never masquerade
  as live data.
- Every `null` renders as a visible italic `null`, never as a blank or a
  plausible-looking substitute. The reasons are in the collapsible
  "could not be determined" list at the bottom.
