---
name: unmassk-electronics
description: >
  Use when the user wants to build or program a real electronics / hardware
  project — "build a hardware gadget", "start an electronics project", "wire up
  a sensor / motor / LED", "make a device that does X", "verify this against the
  real board", "trastear con electrónica" — or is working with any physical
  device (microcontroller, single-board computer, robot) that must be confirmed
  against hardware rather than assumed. Or mentions any of: electronics, hardware
  project, physical device, breadboard, GPIO pin, sensor, actuator, hardware gate,
  device verification, per-device profile, maker, tinker hardware.
  Covers the shared method for agent-driven electronics across three branches —
  microcontroller firmware, Raspberry Pi / Linux single-board computers, and
  hobby robotics. The one rule that unifies them: never report a hardware task
  "done" until the device itself confirms it (a serial assertion, a sensor
  read-back, a service health check). Also sets up the per-device profile (a
  persisted file the agent re-reads every session so it never rediscovers a
  board's constraints by trial and error) and the START-gated toolset install
  (nothing installs until a project is actually an electronics project).
  Use when NOT: designing or 3D-printing a physical part / enclosure with no
  circuit or firmware — that is a different domain (CAD / 3D printing), out of
  scope here. Real-time / web / game 3D graphics are also unrelated.
version: 1.0.0
---

# unmassk-electronics — Agent-Driven Electronics for Makers

Build, program, and **verify real hardware** — a device that boots, a pin that
reads high, a robot that actually moved. Not "the code compiled, so it works."
This is the maker half of the physical world (the other half, designing and
printing the parts, is a separate skill).

## THE PRIME DIRECTIVE — the device confirms, or it is not done

Software lies quietly about hardware. A flash that "succeeded" can boot into a
crash loop; a servo command that returned can have moved nothing; a service that
"started" can be dead a second later. So the rule, in every branch:

> **Never report a hardware task done until the device itself confirms it.**

Confirmation is always a *read back from reality*, never the command you sent:

- **Firmware** → the serial output asserts a success marker and shows no crash
  signature (`Guru Meditation`, `Brownout`, `WDT reset`).
- **Raspberry Pi** → the pin is read back through a second path, the service
  passes a health check, the camera returns a real frame.
- **Robotics** → a sensor (distance, IMU, encoder) reads the expected change
  *after* the move, not the fact that the move command ran.

A hardware task reported "done" on the strength of the command alone is the
self-harm failure this skill exists to prevent — the physical-world version of
a silent failure.

## The three branches

Agent-driven electronics splits into three worlds with different tooling but the
same gate discipline. Build order is micro → Pi → robotics.

1. **Microcontroller firmware** — ESP32 / RP2040 / STM32, C/C++ via PlatformIO.
   The loop is build → flash → read serial → assert. The gate is a runtime
   serial assertion. *(This is the entry point and the first branch built.)*
2. **Raspberry Pi / Linux SBC** — a full Linux computer driven over SSH, Python
   + GPIO. The gate is a read-back through a second path and a service health
   check.
3. **Robotics** — motors, servos, sensors sitting on top of the other two. The
   gate is sensor feedback after every action.

Each branch has its own skill with the specific tooling, patterns, and
references; this core skill carries the shared method they all obey.

## The per-device profile

Hardware has constraints the agent must not rediscover every session (this board
has no keyboard, that pin is reserved, this kernel has a known GPIO bug, this
accelerator is present). Record them in a **persisted per-device profile file**
the agent reads at the start of every session — the same pattern as this
toolkit's own memory: a fact worth keeping is written down, not re-derived by
trial and error against physical hardware.

## The toolset is START-gated

The hardware toolset (PlatformIO, the MCP servers, the Python hardware
libraries) is **not installed until a project is actually an electronics
project**. It installs in the project's START step, per branch — never eagerly.
A branch's setup script declares exactly what it needs; nothing lands on the
machine before there is an electronics project that needs it.

## The honest boundary

The agent writes and verifies the code. It does **not** wire the breadboard,
solder the joints, mount the battery, or calibrate a servo's centre by hand — no
software gate closes a loose jumper wire. "A robot you download fully built"
does not exist. What this skill delivers: correct, idiomatic hardware code, and
a hard refusal to call it working until the device says so.
