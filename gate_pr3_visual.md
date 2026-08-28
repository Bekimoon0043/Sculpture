# gate_pr3_visual.md — PR-3, the operator's eye gate

**Cost: $0.** Nothing here spends money. No AI call is made, and none of
the steps below can trigger one.

**Before you start**, the port binding changed (no image change, so no
rebuild — this just re-publishes the ports):

```powershell
docker compose up -d
```

---

## What changed, in one sentence

The platform used to answer to every device on your network with no
password; it now answers only on your own machine, and everything you do
on the laptop works exactly as before.

## 1. Your own machine still works

- [ ] Open <http://localhost:5173> — the Designer loads.
- [ ] Open one of your **existing** designs from the library and confirm
      the viewport shows it. (Opening a stored design is a local database
      read and a local geometry preview — $0. Do **not** run a Council
      brief for this test.)
- [ ] In PowerShell:

```powershell
Invoke-RestMethod http://localhost:8000/api/health | ConvertTo-Json -Depth 3
```

- [ ] The response shows `"status": "ok"`.

## 2. The network no longer reaches it

Find your laptop's Wi-Fi/LAN address:

```powershell
Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
  Select-Object InterfaceAlias, IPAddress
```

Take the `IPAddress` on your Wi-Fi adapter (it usually looks like
`192.168.x.x`).

- [ ] On your **phone**, connected to the **same Wi-Fi**, open
      `http://<that address>:5173` — it must **fail to load**.
- [ ] Also try `http://<that address>:8000/api/health` — it must **fail
      to load**.
- [ ] Optional, on the laptop itself (proves the same thing without the
      phone): both of these must **fail**:

```powershell
Test-NetConnection <that address> -Port 5173
Test-NetConnection <that address> -Port 8000
```

(`TcpTestSucceeded : False` is the pass.)

## Why this matters

The platform has **no login**. Before this change, anyone on your Wi-Fi
could open your designs, read every AI transcript, and press the buttons
that spend your provider credits. The loopback binding is now the only
lock on that door — which is why the auto gate re-checks it on every
future slice, and why LAN access stays off until the platform has real
authentication (`docs/operator/11_network_privacy.md`).

---

## Sign-off

```
Date:
Ran docker compose up -d first:          yes / no
Step 1 — localhost UI + health ok:       yes / no
Step 2 — phone could NOT reach either:   yes / no
Notes:
```
