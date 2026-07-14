---
name: electronics-micro
description: >
  Use when the user asks to "program an ESP32 / RP2040 / STM32", "write
  firmware", "flash a microcontroller", "build a PlatformIO project", "read the
  serial monitor", "why does my board crash / Guru Meditation / brownout / WDT
  reset", "blink an LED / read a sensor on a microcontroller", "set up an Arduino
  project", or is developing embedded firmware that gets compiled and flashed to
  a chip with no operating system — or mentions any of: microcontroller, ESP32,
  ESP32-S3, RP2040, STM32, nRF52, Arduino, firmware, PlatformIO, pio, flash,
  serial monitor, UART, ESP-IDF, MicroPython, Guru Meditation, watchdog reset,
  brownout, bootloader, embedded C/C++.
  Covers the microcontroller-firmware branch of agent-driven electronics: the
  build → flash → read-serial → assert loop, driven by PlatformIO (the
  platformio-mcp server plus the raw `pio` CLI and `pio test` as the structured
  gate). The hard gate is a runtime serial assertion — the firmware must print a
  success marker and show no crash signature before the flash is called good.
  Also covers ESP32 crash triage (Guru Meditation, stack overflow, brownout,
  WDT) and register-level debug via a probe.
  Use when NOT: driving a Raspberry Pi or other full-Linux single-board computer
  (that runs an OS and is controlled over SSH, not flashed), or wiring
  motor/servo/sensor robotics behaviour — those are separate concerns. Not for
  3D-printing an enclosure for the board.
version: 1.0.0
---

# electronics-micro — Microcontroller Firmware

The entry branch. A microcontroller (ESP32, RP2040, STM32, Arduino) runs one
compiled program with no OS: you write C/C++, compile, flash it over USB, and
watch the serial output. The gate lives in that serial output.

## The loop (with the gate)

```
1. WRITE     firmware in C/C++ (PlatformIO project)                    [agent]
2. BUILD     `pio run` — a link error is a hard gate: can't flash a build       [agent]
             that doesn't compile. (Compile is free verification.)
3. FLASH     upload to the board over USB                              [agent]
4. ⛔GATE: SERIAL ASSERT   open the serial monitor and assert: a success        [agent]
             marker is printed AND no crash signature appears
             (Guru Meditation / Brownout / WDT reset) within a timeout.
             No assertion → NOT done, regardless of a clean flash.
```

Two ways to run the gate, strongest first:

- **`pio test`** — PlatformIO's on-device unit runner (Unity). It builds a test
  firmware, flashes it, opens serial, and parses **structured PASS/FAIL/IGNORE**
  results — real assertion counts, not string-matching. Prefer this when the
  behaviour is testable; it is the most deterministic gate and needs no MCP.
- **`agent_flash_monitor_verify`** (platformio-mcp) — flashes, opens serial, and
  asserts against patterns: `--expect-all BOOT_OK --reject-patterns "Guru
  Meditation,Brownout detector,WDT reset" --timeout 45`. A ready-made runtime
  gate for firmware that just needs a boot/behaviour marker.

## Tooling (installed by this branch's START setup)

| Role | Tool | Note |
| --- | --- | --- |
| MCP driver | **platformio-mcp** (npm, MIT) | board discovery, build, flash, monitor, `agent_flash_monitor_verify`. Board-agnostic (1000+). Young — expect occasional rough edges. |
| Deterministic gate | **`pio` core CLI** + `pio test` | Unity structured pass/fail. Scriptable from Bash; the fallback when the MCP misbehaves. |
| Register debug | **embedded-debugger-mcp** (probe-rs, MIT) | breakpoints / memory / RTT. Solid on STM32 / nRF52 / RISC-V; classic ESP32 (Xtensa) is experimental. |

> **Name check:** the correct npm package is **`platformio-mcp`** (jl-codes) — not
> `platformio-mcp-server` (a near-dead lookalike). See `references/setup.md`.

## Language: C/C++ first

C/C++ via PlatformIO is the primary path **because the compile step is itself a
gate** and `pio test` gives structured on-device assertions. MicroPython /
CircuitPython iterate faster (no compile) but the build gate disappears and
verification collapses onto runtime behaviour only — a weaker gate, and LLMs
generate CircuitPython's more divergent API less reliably. Keep MicroPython as
an optional fast-prototype mode, not the default.

## When to read which reference

- `references/setup.md` — the START setup: what installs (platformio-mcp, pio),
  the package-name gotcha, verification. Read before touching a board.
- `references/esp32-crash-triage.md` — Guru Meditation, stack overflow,
  brownout, WDT, and how `idf.py monitor` auto-decodes backtraces to file:line.
  Read when a board crashes.
- `references/platformio-patterns.md` — project layout, `platformio.ini`, the
  serial-assert and `pio test` gate patterns. Read before writing firmware.

## The honest limit

The board must be wired and plugged in — no gate here checks a breadboard.
Everything above assumes the circuit exists; it verifies the *firmware*, not the
soldering.
