# 11 — Network privacy: who can reach the platform

*(PR-3, ADR-058, 2026-08-27)*

## The short version

Everything runs on your laptop, and **only your laptop can talk to it**.
Your browser uses `http://localhost:5173` (the Designer) and
`http://localhost:8000` (the API) exactly as before. Phones, other
computers, and anything else on your Wi-Fi get nothing — the connection
is refused before any LuxuryForm code even hears about it.

## Why it is locked down

The platform has **no login screen and no passwords** — it was built for
one operator on one machine. Before this change, Docker published its two
ports to every network interface, which meant anyone on the same Wi-Fi
could:

- open and change your designs,
- read every AI conversation, including full prompts and responses,
- press the buttons that make **paid** AI calls on your accounts.

Binding the ports to `127.0.0.1` (the machine's "talk to myself"
address) closes all of that with zero change to how you work.

## What still works, and why

- **The Designer UI** talks to the backend *inside* Docker's private
  network (`http://backend:8000`), which the loopback binding does not
  touch. Nothing about building, validating, costing, rendering or
  exporting changes.
- **Scripts and gates on this machine** use `localhost`, which still
  works — `localhost` *is* the loopback address.
- **The sandboxes** (`geo-worker`, `render-worker`) never had network
  access at all (`network_mode: none`) and are unchanged.

## What keeps it locked

`scripts/gate_pr3_auto.py` runs with the rest of the auto-gate roster on
every slice. It fails loudly if any compose service ever publishes a port
on anything but `127.0.0.1` — and, run on the host, it also checks the
*actual sockets*: your machine's network addresses must refuse
connections to 8000 and 5173. A regression here would otherwise be
completely silent (everything on the laptop would keep working), which is
exactly why the check is automatic and standing.

## If you ever want access from another device

**LAN or remote access is unsupported.** There is deliberately no
switch, no override file and no documented command for it in the current
platform — with no authentication, opening the port IS handing out your
designs and your AI spending to the network.

It can return only as part of a future, deliberate slice that ships
authentication first (a real login in front of every API route), and
that slice would update this page. If you need something from the
platform on another device today, export it (the LUXEXCHANGE package,
renders, the BOM document) and move the file.
