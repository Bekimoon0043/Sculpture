# Starting the Platform — Windows Step by Step

Plain-language guide. You do not need to know programming. Follow the steps
in order; copy the commands exactly as written.

**Time:** 30–90 minutes the first time, depending on connection speed
(mostly Docker downloading; on a ~320 kB/s line expect the longer end).
**Cost:** each gate run costs about **$0.01–0.05** in AI API calls.

---

## Step 1 — Install Docker Desktop

1. Go to https://www.docker.com/products/docker-desktop/ and click
   **Download for Windows**.
2. Run the installer. Accept the defaults. Restart the computer if asked.
3. Open **Docker Desktop** and wait until it says it is running (the whale
   icon in the system tray stops animating).

## Step 2 — Get the LuxuryForm folder

Put the `luxuryform` folder somewhere easy to find, e.g. `C:\luxuryform`.
Everything below happens inside that folder.

## Step 3 — Create your .env file and paste the three API keys

1. Open **Command Prompt** (press Win+R, type `cmd`, press Enter).
2. Go into the folder:

   ```bat
   cd C:\luxuryform
   ```

3. Make your private key file:

   ```bat
   copy .env.example .env
   ```

4. Open the new file:

   ```bat
   notepad .env
   ```

5. Paste your real keys after the `=` signs, so it looks like:

   ```
   ANTHROPIC_API_KEY=sk-ant-xxxxxxxx
   OPENAI_API_KEY=sk-xxxxxxxx
   MOONSHOT_API_KEY=sk-xxxxxxxx
   ```

   - Anthropic key: https://console.anthropic.com/ (API keys section)
   - OpenAI key: https://platform.openai.com/api-keys
   - Moonshot/Kimi key: https://platform.moonshot.ai/ (API keys section)

   No quotes, no spaces around the `=`. Save and close Notepad.
   **Never email or share this file.**

## Step 4 — Start the platform

In the same Command Prompt:

```bat
docker compose up --build -d
```

The first run downloads and builds for a while — on a slow connection this
can be an hour or more (mostly one large ~300 MB download). When it returns
to the prompt, check it is alive: open a browser and go to
**http://localhost:8000/api/health** — you should see a page of status text
starting with `"status": "ok"`.

**If the build stops with a network error (connection dropped, timeout):**
just run the exact same command again:

```bat
docker compose up --build -d
```

The build downloads in separate stages, largest first. Every stage that
finished is kept — the retry only repeats the one stage that was
interrupted, never the whole build. Repeat until it completes.

**Optional — different package server:** the build downloads Python packages
from PyPI by default. If you are told to use a specific mirror, set it once
before building (Git Bash: `export PIP_INDEX_URL=https://address/simple`;
Command Prompt: `set PIP_INDEX_URL=https://address/simple`), then run the
same build command. No mirror is recommended by default — coverage varies
by location, and a mirror that works elsewhere may not have our exact
package versions here.

**The Debian files come from a permanent archive by default:** the build
also downloads 9 small system-library files (about 1.6 MB total). By
default they now come from a dated snapshot of the Debian archive, which
keeps these exact versions permanently — the regular servers rotate old
versions away, which broke this stage before. Each download prints its own
address as it goes, so if one fails, the last printed line names the exact
file.

**Optional — different Debian server (Plan A):** if the snapshot server is
unreachable from your network, point the build at any Debian mirror that
has the exact pinned versions — Command Prompt:

```bat
set DEB_POOL_URL=https://your.mirror/debian/pool/main/
docker compose build backend
```

The files are checksum-pinned, so a mirror only carries bytes: if anything
is wrong, the build stops and names the file. Nothing bad can slip through.
If a mirror is missing a file, the build fails fast (about 10 seconds into
that stage) and the last `GL-LAYER download:` line names it — try a
different mirror.

**Optional — no Debian server at all (Plan B):** if no Debian mirror works
but Docker Hub does, use the donor variant, which takes the same 9
libraries from another Docker image instead. First pick a donor image with
the one-line check printed at the top of `Dockerfile.donor`, then:

```bat
set BACKEND_DOCKERFILE=Dockerfile.donor
set GL_DONOR_IMAGE=eclipse-temurin:21-jdk-noble
docker compose build backend
docker compose up -d backend
```

(Use the image name that passed the check. `set BACKEND_DOCKERFILE=` —
empty — returns to the normal build.)

## Step 5 — Run the Phase 1 acceptance gate

```bat
docker compose exec backend python scripts/gate_phase1.py
```

(If you have a Python 3.11 environment on the machine itself, the same gate
also runs directly: `python scripts\gate_phase1.py` — inside Docker is the
recommended way.)

The gate prints six numbered sections, then a verdict. It sends one small
text prompt and one small test image to each provider, proves the spend cap
halts a run, and shows the database rows it wrote as proof.

## What the verdicts mean

- **`PHASE 1 GATE: PASS`** — all three providers answered (text AND vision),
  every call was logged, and the spend cap provably halts a run. Phase 1 is
  accepted.
- **`PHASE 1 GATE: FAIL — <provider>: not configured (set XXXX_API_KEY in .env)`**
  — a key is missing. Open `notepad .env`, paste that exact key, then run the
  gate command again. This is the most common message and is easy to fix.
- **`PHASE 1 GATE: FAIL — <provider>: <some API error>`** — the provider
  rejected the call. Usual causes: no billing credit on that account, or the
  model name in `config\council.yaml` is not available on your account. Fix
  the account, or edit `model_defaults` in `config\council.yaml` to a model
  your account can use, and re-run the gate.
- **`FAIL — <provider> vision: <error>`** — the provider's image endpoint
  failed. The gate also prints an ACTION line: copy the error into
  `LIMITATIONS.md` section 6 right away, then tell the technical lead.

## Useful everyday commands

```bat
docker compose logs -f backend     REM watch what the platform is doing (Ctrl+C to stop watching)
docker compose down                REM stop the platform
docker compose up -d               REM start it again (fast after the first build)
```

Browse the audit log in your browser:
- http://localhost:8000/api/logs/calls — every AI call with full prompt,
  response, tokens and cost
- http://localhost:8000/api/logs/budget — today's spend, the caps, and any
  cap-breach events
