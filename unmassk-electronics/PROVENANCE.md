# Provenance

This plugin is **original work, not a lift.** Unlike some sibling plugins that
fused prior Claude skills, there was no existing skill to adapt for this domain —
the agent-driven-electronics skill ecosystem is genuinely sparse. The method (the
"the device confirms or it is not done" prime directive, the three-branch split,
the per-branch gates, the per-device profile, the START-gated toolset) and every
SKILL.md and reference were written from scratch, from a verified research pass.

## What was synthesized, and from where

Three parallel research passes (2026-07-14) surveyed the current best-in-class
agent-first tooling for each branch, verified licenses/maturity/last-activity
against primary sources (GitHub/npm APIs, official docs), and distilled a
shortlist. The tool choices and facts in the references come from that pass, each
uncertain claim flagged in place:

| Branch | Verified core finding |
|---|---|
| Microcontroller | `platformio-mcp` (jl-codes, MIT) ships `agent_flash_monitor_verify` — a literal serial-assert gate; `pio test` is the stronger structured fallback. Package-name gotcha vs the near-dead `platformio-mcp-server` recorded. |
| Raspberry Pi | No mature Pi-specific MCP exists; plain SSH + `gpiozero` + `pinctrl` read-back is the battle-tested pattern. `RPi.GPIO` deprecated on Pi 5; `lgpio`/kernel-6.6.45 pin-misread bug recorded. |
| Robotics | No mature agent-first robotics tooling outside ROS2; ROS2 is overkill to start. Adafruit CircuitPython spans ESP32+Pi with one API. |

No files were copied from any repository; the tools above are dependencies the
plugin *drives*, not sources it lifts from.

## Honesty about maturity

The references state, in place, that this ecosystem is young — `platformio-mcp`
is ~40 stars / single-maintainer; the Pi/robotics MCP options are sub-50-star or
unreleased. The plugin deliberately keeps deterministic CLI fallbacks (`pio
test`, `pinctrl`, our own `serial_verify.py`) so it does not depend on the
youngest links. And it states plainly, in every branch, the hard boundary: the
agent writes and verifies code; **nobody wires or solders the hardware for you.**

## Reconciling drift

Tool maturity and "recommended library" facts here go stale fast (gpiozero over
RPi.GPIO, picamera2 via apt, platformio-mcp version). When they change, re-run
the research pass, diff against these references, and fold in new facts —
keeping every spec/version claim sourced and date-checked, never asserted from
memory.
