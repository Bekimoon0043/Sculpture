#!/usr/bin/env python3
"""PR-3 AUTO GATE — loopback-only network exposure. $0, non-interactive.

The API has no authentication (LIMITATIONS §19), so the host port binding
is the platform's ONLY access control. This gate proves, and keeps
proving on every roster run, that the default deployment answers on the
operator's own machine and nowhere else (ADR-058).

Two EXPLICIT sections, in different environments — like gate_phase14_auto,
each run prints exactly which sections it covered, an unrunnable section
reports NOT RUN with the command to run it elsewhere, and a NOT RUN
section can never support an overall full-gate PASS:

* STATIC — parse docker-compose.yml and assert the bindings. Needs
  PyYAML, so run it inside the backend container — and pipe the HOST's
  live compose file in, because the copy baked into the image at build
  time is exactly the stale snapshot this gate must never trust (the
  host file governs what `docker compose up` publishes):
      Get-Content docker-compose.yml -Raw | docker compose exec -T backend python scripts/gate_pr3_auto.py --static --stdin
* LIVE — observe the ACTUAL sockets on the operator's machine (config
  intent is not enough: Docker must be seen honouring it). Stdlib only,
  so run it on the host:
      python scripts\\gate_pr3_auto.py --live
  Checks: 127.0.0.1:8000/api/health returns the real healthy JSON;
  127.0.0.1:5173 serves the LuxuryForm frontend; every non-loopback IPv4
  address on the machine REFUSES TCP connects to 8000 and 5173. With no
  non-loopback IPv4 address present the LAN sub-check is NOT RUN — it
  never passes vacuously.

PR-3 closure requires BOTH sections run and green. No flag = attempt
both, honestly reporting whichever cannot run here.

Exit 0: every section that ran passed, and at least one section ran.
Exit 1: any check failed, or nothing could run.
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"

LOOPBACK_HOST = "127.0.0.1"
PUBLISHED_PORTS = (8000, 5173)

#: Judgement value: per-connect timeout for the live socket checks. This
#: affects gate RUNTIME only, never correctness — a service that takes
#: longer than this to ACCEPT on loopback is broken in its own right, and
#: a LAN connect that hangs past it is treated as not-answering, which is
#: the passing outcome anyway.
CONNECT_TIMEOUT_S = 2.0

#: Judgement value: how long the positive loopback checks wait for a
#: service that is still BOOTING. Measured need: a roster run right after
#: `docker compose up --build -d` hit the backend mid-recreate twice
#: (docker-proxy accepts, then closes -- RemoteDisconnected) while the
#: same URL answered healthy seconds later. The gate retries until this
#: deadline, printing each attempt, then fails loudly -- a service that
#: cannot become healthy in 60 s on this machine is broken, not booting.
STARTUP_DEADLINE_S = 60.0
STARTUP_RETRY_INTERVAL_S = 3.0

#: What the real services identify themselves with (ground truth read
#: from routes_health.py and frontend/index.html, 2026-08-27).
HEALTH_EXPECTED_STATUS = "ok"
FRONTEND_MARKER = "LuxuryForm Studio"


def _say(msg: str) -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# STATIC section — the compose file says loopback, for every service
# ---------------------------------------------------------------------------

_STATIC_COMMAND = (
    "  Get-Content docker-compose.yml -Raw | docker compose exec -T "
    "backend python scripts/gate_pr3_auto.py --static --stdin"
)


def run_static(use_stdin: bool) -> bool | None:
    """True = pass, False = fail, None = NOT RUN in this environment."""
    try:
        import yaml  # type: ignore
    except ImportError:
        _say("STATIC: NOT RUN — PyYAML is not importable here. Run:")
        _say(_STATIC_COMMAND)
        return None

    if use_stdin:
        _say("STATIC: parsing docker-compose.yml from stdin (the HOST's "
             "live file)")
        text = sys.stdin.read()
    elif Path("/.dockerenv").exists():
        # The image carries a docker-compose.yml (COPY . .), but it is the
        # BUILD-TIME snapshot — asserting it could pass while the host's
        # governing file has regressed, the silent hole this gate exists
        # to close. Refuse it and name the honest invocation.
        _say("STATIC: NOT RUN — inside the container only the build-time "
             "copy of docker-compose.yml is visible, and the HOST's file "
             "is what governs the published ports. Pipe the live file in:")
        _say(_STATIC_COMMAND)
        return None
    else:
        _say(f"STATIC: parsing {COMPOSE_PATH}")
        text = COMPOSE_PATH.read_text(encoding="utf-8")

    doc = yaml.safe_load(text)
    services = doc.get("services") or {}
    ok = True

    for name, svc in sorted(services.items()):
        ports = (svc or {}).get("ports") or []
        for entry in ports:
            text = str(entry)
            # Accepted form: 127.0.0.1:HOST:CONTAINER (long-syntax dicts
            # would arrive as dicts — refuse them so a future rewrite must
            # come through this gate deliberately).
            if not isinstance(entry, str):
                _say(f"  FAIL {name}: non-string ports entry {entry!r} — "
                     f"use the '127.0.0.1:host:container' string form")
                ok = False
                continue
            parts = text.split(":")
            if len(parts) != 3 or parts[0] != LOOPBACK_HOST:
                _say(f"  FAIL {name}: published on {text!r} — every host "
                     f"publish must bind {LOOPBACK_HOST} (3-part form)")
                ok = False
            else:
                _say(f"  ok   {name}: ports {text!r} is loopback-bound")

    for worker in ("geo-worker", "render-worker"):
        svc = services.get(worker)
        if svc is None:
            _say(f"  FAIL {worker}: service missing from compose")
            ok = False
            continue
        if svc.get("network_mode") != "none":
            _say(f"  FAIL {worker}: network_mode is "
                 f"{svc.get('network_mode')!r}, expected 'none'")
            ok = False
        elif svc.get("ports"):
            _say(f"  FAIL {worker}: declares ports {svc.get('ports')!r}")
            ok = False
        else:
            _say(f"  ok   {worker}: network_mode none, no ports")

    frontend = services.get("frontend") or {}
    env = frontend.get("environment") or []
    env_map = {}
    if isinstance(env, dict):
        env_map = {str(k): str(v) for k, v in env.items()}
    else:
        for item in env:
            key, _, value = str(item).partition("=")
            env_map[key] = value
    target = env_map.get("VITE_API_TARGET", "")
    if target == "http://backend:8000":
        _say(f"  ok   frontend: VITE_API_TARGET={target!r} (service DNS — "
             f"the UI never crosses a host port, so loopback cannot break it)")
    else:
        _say(f"  FAIL frontend: VITE_API_TARGET={target!r}, expected "
             f"'http://backend:8000' — anything else may route UI traffic "
             f"through a host port and quietly depend on the binding")
        ok = False

    _say(f"STATIC: {'PASS' if ok else 'FAIL'}")
    return ok


# ---------------------------------------------------------------------------
# LIVE section — the machine's actual sockets behave as the file claims
# ---------------------------------------------------------------------------

def _http_get(url: str) -> tuple[int, str]:
    with urllib.request.urlopen(url, timeout=CONNECT_TIMEOUT_S * 3) as resp:
        return resp.status, resp.read(65536).decode("utf-8", errors="replace")


def _tcp_answers(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=CONNECT_TIMEOUT_S):
            return True
    except OSError:
        return False


def _non_loopback_ipv4() -> list[str]:
    addresses: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None,
                                       socket.AF_INET):
            addresses.add(info[4][0])
    except OSError:
        pass
    # A UDP "connection" to a public address reveals the default-route
    # interface address without sending a packet.
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(("192.0.2.1", 9))  # TEST-NET-1, never routed
            addresses.add(probe.getsockname()[0])
        finally:
            probe.close()
    except OSError:
        pass
    return sorted(a for a in addresses
                  if not a.startswith("127.") and not a.startswith("169.254."))


def run_live() -> dict[str, bool | None]:
    """Two sub-sections: 'live-loopback' and 'live-lan'.

    True = pass, False = fail, None = NOT RUN. The LAN sub-check is None
    when the machine has no non-loopback IPv4 address — it never passes
    vacuously (there was nothing to prove refusal against).
    """
    if Path("/.dockerenv").exists():
        _say("LIVE: NOT RUN — this is inside a container, which cannot see "
             "the HOST's sockets. Run on the host:")
        _say(r"  python scripts\gate_pr3_auto.py --live")
        return {"live-loopback": None, "live-lan": None}

    ok = True
    _say("LIVE: positive checks on loopback — the real services, not just "
         "open ports (booting services are retried until "
         f"{STARTUP_DEADLINE_S:.0f} s, then failed loudly)")

    def _check_with_deadline(label: str, probe) -> bool:
        import time
        deadline = time.monotonic() + STARTUP_DEADLINE_S
        attempt = 0
        while True:
            attempt += 1
            failure = probe(attempt)
            if failure is None:
                return True
            if time.monotonic() >= deadline:
                _say(f"  FAIL {label} after {attempt} attempts over "
                     f"{STARTUP_DEADLINE_S:.0f} s: {failure}")
                return False
            time.sleep(STARTUP_RETRY_INTERVAL_S)

    def _health_probe(attempt: int) -> str | None:
        try:
            status, body = _http_get(f"http://{LOOPBACK_HOST}:8000/api/health")
            payload = json.loads(body)
        except Exception as exc:
            return f"{type(exc).__name__}: {exc}"
        if status == 200 and payload.get("status") == HEALTH_EXPECTED_STATUS:
            _say(f"  ok   {LOOPBACK_HOST}:8000/api/health -> HTTP {status}, "
                 f"status={payload.get('status')!r}, "
                 f"db.ok={payload.get('db', {}).get('ok')!r} "
                 f"(attempt {attempt})")
            return None
        return (f"HTTP {status}, payload status={payload.get('status')!r} "
                f"(expected {HEALTH_EXPECTED_STATUS!r}): {body[:300]}")

    def _frontend_probe(attempt: int) -> str | None:
        try:
            status, body = _http_get(f"http://{LOOPBACK_HOST}:5173/")
        except Exception as exc:
            return f"{type(exc).__name__}: {exc}"
        if status == 200 and FRONTEND_MARKER in body:
            _say(f"  ok   {LOOPBACK_HOST}:5173/ -> HTTP {status}, serves "
                 f"{FRONTEND_MARKER!r} (attempt {attempt})")
            return None
        return (f"HTTP {status}, marker {FRONTEND_MARKER!r} not found in "
                f"first 64 kB")

    if not _check_with_deadline(f"{LOOPBACK_HOST}:8000/api/health",
                                _health_probe):
        ok = False
    if not _check_with_deadline(f"{LOOPBACK_HOST}:5173/", _frontend_probe):
        ok = False

    results: dict[str, bool | None] = {"live-loopback": ok}
    _say(f"LIVE loopback: {'PASS' if ok else 'FAIL'}")

    addresses = _non_loopback_ipv4()
    if not addresses:
        _say("LIVE LAN: NOT RUN — no non-loopback IPv4 address is present "
             "on this machine right now, so there is nothing to prove "
             "refusal against. This sub-check never passes vacuously; "
             "connect the machine to a network and re-run.")
        results["live-lan"] = None
        return results

    lan_ok = True
    _say(f"LIVE LAN: negative checks — every non-loopback IPv4 must REFUSE "
         f"{PUBLISHED_PORTS}: {addresses}")
    for address in addresses:
        for port in PUBLISHED_PORTS:
            if _tcp_answers(address, port):
                _say(f"  FAIL {address}:{port} ANSWERED a TCP connect — the "
                     f"platform is reachable from the network")
                lan_ok = False
            else:
                _say(f"  ok   {address}:{port} refused "
                     f"(timeout {CONNECT_TIMEOUT_S}s)")
    _say(f"LIVE LAN: {'PASS' if lan_ok else 'FAIL'}")
    results["live-lan"] = lan_ok
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--static", action="store_true", dest="static_only",
                        help="run only the compose-file assertions")
    parser.add_argument("--live", action="store_true", dest="live_only",
                        help="run only the host socket observations")
    parser.add_argument("--stdin", action="store_true", dest="use_stdin",
                        help="read docker-compose.yml text from stdin "
                             "(the in-container invocation pipes the "
                             "host's live file)")
    args = parser.parse_args()

    want_static = not args.live_only
    want_live = not args.static_only

    results: dict[str, bool | None] = {}
    if want_static:
        results["static"] = run_static(args.use_stdin)
    else:
        _say("STATIC: NOT RUN in this invocation (--live)")
        results["static"] = None
    if want_live:
        results.update(run_live())
    else:
        _say("LIVE: NOT RUN in this invocation (--static)")
        results["live-loopback"] = None
        results["live-lan"] = None

    ran = {k: v for k, v in results.items() if v is not None}
    not_run = sorted(k for k, v in results.items() if v is None)
    _say("")
    _say(f"sections run: {', '.join(sorted(ran)) if ran else 'none'}")
    if not_run:
        _say(f"NOT covered in this run: {', '.join(not_run)} — PR-3 "
             f"closure requires static, live-loopback AND live-lan green; "
             f"see commands above.")
    if not ran:
        _say("FAIL — no section could run here.")
        return 1
    if all(ran.values()):
        _say("PASS — all sections that ran passed at $0 with no network "
             "beyond this machine's own interfaces.")
        return 0
    _say("FAIL — a section that ran did not pass. Details above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
