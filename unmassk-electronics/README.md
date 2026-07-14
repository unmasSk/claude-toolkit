# unmassk-electronics

**Agent-driven electronics for makers.** Build, program, and *verify real
hardware* — a board that boots, a pin that reads high, a robot that actually
moved — not "the code compiled, so it works."

This is the maker half of the physical world. (Designing and 3D-printing the
parts is a separate skill, `unmassk-3d`.)

## The one rule

**Never report a hardware task done until the device itself confirms it.** Every
branch enforces it, and confirmation is always a read back *from reality*, never
the command you sent:

- **Firmware** → the serial output asserts a success marker and shows no crash
  signature (Guru Meditation / Brownout / WDT).
- **Raspberry Pi** → the pin is read back through a second path (`pinctrl`), the
  service passes a health check.
- **Robotics** → a sensor (distance, IMU, encoder) reads the expected change
  *after* the move.

A hardware task called "done" on the strength of the command alone is the
physical-world version of a silent failure — exactly what this skill refuses.

## Three branches (built micro → Pi → robotics)

| Branch | World | Gate |
|---|---|---|
| **electronics-micro** | Microcontroller firmware (ESP32/RP2040/STM32, PlatformIO) | serial assert (`pio test` / `agent_flash_monitor_verify`) |
| **electronics-pi** | Raspberry Pi / Linux SBC (SSH + gpiozero) | pin read-back + service health check |
| **electronics-robotics** | Motors, servos, sensors (on top of the two above) | sensor read-back after every action |

The core skill (`unmassk-electronics`) carries the shared method: the prime
directive, the per-device profile (a persisted file the agent re-reads each
session so it never rediscovers a board's constraints), and the **START-gated
toolset** — nothing installs until a project is actually an electronics project.

## What you interact with

You describe what you want to build; the agent writes the firmware/Python, drives
the board, and verifies it against real feedback. You provide the two things no
software can: the **hardware, wired** — and the honesty that the agent won't call
a movement "done" without a sensor confirming it.

## Honest limits

Nobody downloads a finished robot. The agent writes and verifies the code; it
does **not** wire the breadboard, solder the joints, size the motor driver, or
calibrate a servo centre by hand. And the tooling here is young — the plugin
keeps deterministic CLI fallbacks (`pio test`, `pinctrl`, `serial_verify.py`) so
it doesn't hang on the newest, least-proven links.

## License

MIT — see `LICENSE`. Method original; drives open-source tools and was built from
a verified research pass — see `CREDITS.md` and `PROVENANCE.md`.
