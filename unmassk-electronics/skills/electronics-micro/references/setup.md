# Setup — the START step of a microcontroller project

Run this **only when a project is actually a microcontroller/firmware project** —
the toolset is START-gated, nothing installs eagerly. The automated installer is
`scripts/setup_micro_env.py`; this reference is the human-readable contract of
what it must do. Check first, install only what is missing.

## 1. PlatformIO Core (the substrate)

```bash
# PlatformIO Core CLI — the build/flash/test engine everything sits on
python3 -m pip install --user platformio        # provides `pio`
pio --version
```

`pio` gives you `pio run` (build), `pio run -t upload` (flash), `pio device
monitor` (serial), and — the deterministic gate — **`pio test`** (on-device
Unity assertions). This alone closes the loop; the MCP below is a convenience on
top.

## 2. platformio-mcp (the MCP driver)

### Activate the MCP (on-demand — Claude drives this)

The platformio MCP is **not connected by default**. The first time this skill
needs it, Claude registers it, then tells the user to restart. Claude runs
these steps and guides the user — the user only restarts when told.

**Before using this tool, check its `mcp__platformio__*` tools are actually
available.** If they are not, the server is not installed/loaded — run the
registration below and tell the user to restart; never proceed as if
platformio-mcp were available without the tool actually present (fall back to
`pio`/`serial_verify.py` instead).

1. **Register the server** (once, user scope — available in every project):
   ```
   claude mcp add platformio --scope user -- npx -y platformio-mcp
   ```
2. **Restart Claude Code.** MCP servers only start at boot; there is no hot
   activation.
3. **API key:** none — platformio-mcp needs no key.

This is the standard on-demand shape for every MCP in the toolkit: register →
restart → (key if needed).

**Package-name gotcha (verified):** the correct package is **`platformio-mcp`**
(jl-codes, MIT, actively maintained). Do **not** install `platformio-mcp-server`
(a near-dead lookalike, 2 stars, no assertion feature). They are different repos
with confusable names.

It exposes `agent_flash_monitor_verify` (the runtime serial-assert gate),
`agent_build_diagnose`, `agent_safe_pin_audit`, and the standard
devices/boards/build/flash/monitor tools. Board-agnostic (1000+ boards via
PlatformIO's DB). It is young (~40 stars, single maintainer) — expect the
occasional rough edge and keep `pio test` as the fallback gate.

## 3. Register-level debug (optional, second-tier)

```bash
# probe-rs-based debugger MCP — breakpoints, memory, RTT
# Solid on STM32 / nRF52 / RISC-V; classic ESP32 (Xtensa) is experimental.
```

Install `embedded-debugger-mcp` (probe-rs, MIT) only if a project needs
breakpoint/register debugging beyond serial. Skip it for typical ESP32 work.

## 4. Verify (don't trust, check)

```bash
pio --version && python3 -c "import serial; print('pyserial', serial.__version__)"
```

`pyserial` backs the fallback `scripts/serial_verify.py` gate. If either is
missing, install before proceeding — a half-installed toolchain is a silent
failure waiting to happen mid-flash.

## 5. Off-computer / manual (cannot be auto-installed)

- **A board** (ESP32 / RP2040 / STM32…), **wired and plugged in over USB**. No
  software here checks the wiring.
- On Linux, serial-port access needs the user in the `dialout` group
  (`sudo usermod -aG dialout $USER`, then re-login) — report this, don't assume
  it is done.

## 6. Deferred / per-project

Board-specific config (`platformio.ini` `board = ...`, `upload_port`,
`monitor_speed`) is written per project, not installed globally — see
`references/platformio-patterns.md`.
