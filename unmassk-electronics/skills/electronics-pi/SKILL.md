---
name: electronics-pi
description: >
  Use when the user asks to "set up a Raspberry Pi", "control GPIO on a Pi",
  "read a sensor / drive a pin from Python on a Raspberry Pi", "use gpiozero",
  "run headless Raspberry Pi", "deploy a service on a Pi", "capture from the Pi
  camera", "SSH into my Pi and…", or is driving a Raspberry Pi or similar
  single-board computer that runs a full Linux OS (not flashed firmware) — or
  mentions any of: Raspberry Pi, Pi 5, Pi Zero, single-board computer, SBC,
  gpiozero, pinctrl, lgpio, picamera2, Raspberry Pi OS, headless Pi, systemd
  service on Pi, GPIO from Python, Blinka.
  Covers the Raspberry-Pi / Linux-SBC branch of agent-driven electronics: the
  agent drives the Pi over SSH with Python, not by flashing firmware. The gate
  is a read-back through a second path (write a pin with gpiozero, confirm it
  with `pinctrl get`) and a service health check, never the command alone. Also
  covers headless provisioning, the camera stack, and the recommended GPIO
  library (gpiozero, since RPi.GPIO is deprecated on Pi 5).
  Use when NOT: programming a microcontroller that gets compiled and flashed
  (ESP32/RP2040/STM32 firmware — no OS, different tooling), or wiring
  motor/servo/sensor robotics behaviour on top. Not for 3D-printing a case.
version: 1.0.0
---

# electronics-pi — Raspberry Pi / Linux SBC

A Raspberry Pi is a **full Linux computer**, not a microcontroller. You don't
flash it — you SSH in and run Python. The gate is: confirm the running system's
state through a second, independent path.

## How the agent drives a Pi

There is no mature Pi-specific control MCP — the battle-tested pattern is
**plain SSH exec** (the Bash tool running `ssh pi@host '<cmd>'`, or a thin SSH
MCP wrapper). Everything below is a command the agent runs over that channel.

## The gate: read back through a second path

Writing a pin and trusting the write is the silent-failure trap — the library
itself can be wrong (there is a known `lgpio` / kernel bug that silently misreads
pins on Pi 5). So:

```
1. WRITE     set the pin with gpiozero (Python)                        [agent]
2. ⛔GATE: READ-BACK   confirm it with a DIFFERENT path — `pinctrl get <pin>`     [agent]
             — before claiming the pin is set. Write via one path, verify via
             another; never trust a single library's own report.
3. SERVICE   for a deployed service: `systemd-analyze verify <unit>` pre-flight,
             then start, then a health check (curl the endpoint / read the log)
             as `ExecStartPost` — done means the health check passed, not that
             `systemctl start` returned.
```

## Tooling (installed by this branch's START setup)

| Role | Tool | Note |
| --- | --- | --- |
| GPIO (primary) | **gpiozero** | Officially recommended, all Pi models, auto-selects backend. `RPi.GPIO` is **deprecated / broken on Pi 5** — do not use it for new work. |
| GPIO read-back gate | **`pinctrl get <pin>`** | independent CLI read of pin state — the second path the gate needs. |
| I2C / SPI / serial | `smbus2` / `spidev` / `pyserial` | current standards. |
| Camera | **picamera2** | install via `apt`, not `pip` (keep it libcamera-version-matched). Gate a capture by asserting a real frame (non-trivial file size / valid header), not "process exited 0". |
| On-device AI | OpenCV (basic) / **Hailo AI Kit** (real-time) | Coral is dead — don't recommend it. Hailo only when real-time detection is the actual goal. |

## Headless provisioning

Use Raspberry Pi Imager's Advanced Options (gear icon) to preconfigure SSH,
Wi-Fi, and user at flash time — a monitor is never required. See
`references/setup.md`.

## The per-device profile matters most here

A Pi build report's recurring failure was the agent forgetting device
constraints (no keyboard, touch-only, specific accelerator present, kernel
version with the GPIO bug). Record it as a `memo(device/<id>)` (objective
profile — see the core skill) so it's re-read every session, not rediscovered
by trial and error over SSH.

## When to read which reference

- `references/setup.md` — START setup: SSH, gpiozero, picamera2, headless imager,
  the `dialout`/`gpio` group notes. Read before touching a Pi.
- `references/gpio-gate.md` — the write-then-read-back gate, `pinctrl`, the
  lgpio/kernel gotcha. Read before driving pins.
- `references/pi-deploy.md` — systemd services with health-check gates, Docker
  caveats. Read before deploying anything long-running.

## The honest limit

If SSH is down (bad network, corrupt OS), the loop is broken by definition —
that needs a physical re-flash or console. And the agent can detect the
*absence* of an I2C device, but not *why* a wire is loose.
