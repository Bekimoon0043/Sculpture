# Docker PATH Setup — Windows Operator Machine

**When to read this:** `docker` is not found in Git Bash, even though Docker Desktop is installed and working (e.g. `docker run hello-world` works from PowerShell or Command Prompt).

---

## The symptom

From Git Bash (MINGW64):

```bash
$ docker --version
bash: docker: command not found
```

From PowerShell or Command Prompt:

```powershell
PS> docker --version
Docker version 29.6.2, build dfc4efb
```

Docker Desktop is installed, but Git Bash does not inherit the same PATH.

---

## Where Docker Desktop actually lives

On the operator machine the Docker CLI and its credential helper are here:

```
C:\Users\buroo\AppData\Local\Programs\DockerDesktop\resources\bin\
```

That directory contains at minimum:

- `docker.exe`
- `docker-credential-desktop.exe`
- `docker-compose.exe`

The `docker-credential-desktop` helper is required. Without it, builds fail with:

```
error getting credentials - err: exec: "docker-credential-desktop":
executable file not found in %PATH%
```

---

## Quick fix for one session

In Git Bash, export PATH before any `docker` command:

```bash
export PATH="/c/Users/buroo/AppData/Local/Programs/DockerDesktop/resources/bin:$PATH"
docker --version
```

Then run the gate loop normally:

```bash
cd /c/Users/buroo/luxuryform
git pull
export PATH="/c/Users/buroo/AppData/Local/Programs/DockerDesktop/resources/bin:$PATH"
docker compose up --build -d
docker compose exec backend python scripts/gate_phase1.py
```

---

## Persistent fix

Add the line to `~/.bashrc` so every new Git Bash window has it:

```bash
echo 'export PATH="/c/Users/buroo/AppData/Local/Programs/DockerDesktop/resources/bin:$PATH"' >> ~/.bashrc
```

Restart Git Bash or run `source ~/.bashrc`.

---

## Verifying both commands work

```bash
export PATH="/c/Users/buroo/AppData/Local/Programs/DockerDesktop/resources/bin:$PATH"
docker --version
docker-credential-desktop --version
```

Both should print a version string. If either is missing, Docker Desktop is not fully installed or a different per-user install path was chosen.

---

## Why this matters for the gate agent

A separate local execution agent (non-interactive, no prompts, all output to stdout) runs the build-and-gate loop on this machine. The agent operates in Git Bash. If the PATH is not set, the loop fails at `docker compose up` with:

```
bash: docker: command not found
```

or, if only `docker.exe` is found but not the credential helper:

```
error getting credentials - err: exec: "docker-credential-desktop":
executable file not found in %PATH%
```

Both errors are preventable by ensuring the full `resources/bin` directory is on PATH before the agent starts.

---

## Gate script contract

All gate scripts are written for a non-interactive agent:

- **No prompts.** No `input()`, no `getpass()`, no `click.confirm()`.
- **No required stdin.** All configuration comes from `.env`, config files, or CLI flags with defaults.
- **Clear exit codes.** `exit 0` on PASS, `exit 1` on FAIL. The agent reads the exact exit code.
- **All output to stdout.** Every result, row dump, and verdict line is printed. The agent reports the full verbatim transcript.
- **Deterministic where possible.** Same code + same environment → same output.

The operator's agent loop is:

1. `git pull`
2. `docker compose up --build -d`
3. `docker compose exec backend python scripts/gate_phase<N>.py`
4. Report the FULL verbatim output. Never summarise a gate result.
