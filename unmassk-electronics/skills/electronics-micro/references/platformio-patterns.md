# PlatformIO patterns — project layout and the gate

Read before writing firmware. The point of PlatformIO here is that **the build
is deterministic and the gate is scriptable** — no clicking through an IDE.

## Project layout

```
firmware/
  platformio.ini        # board, framework, monitor speed, deps
  src/main.cpp          # the firmware
  test/                 # pio test — on-device Unity tests (the strong gate)
  lib/                  # project-private libraries
```

## `platformio.ini`

```ini
[env:esp32dev]
platform = espressif32
board = esp32dev            ; from `pio boards` — never guessed
framework = arduino        ; or espidf
monitor_speed = 115200
monitor_filters = esp32_exception_decoder   ; decode backtraces to file:line
test_framework = unity
```

Every board-specific value (`board`, `upload_port`, `monitor_speed`) comes from
`pio boards` / `pio device list` — read from the connected hardware, never
assumed. Record the confirmed board in the per-device profile (see the core
skill).

## The two gates, strongest first

### 1. `pio test` — structured on-device assertions (preferred)

```cpp
// test/test_main.cpp
#include <unity.h>
void test_led_pin_is_output(void) { TEST_ASSERT_EQUAL(OUTPUT, ...); }
void setup() { UNITY_BEGIN(); RUN_TEST(test_led_pin_is_output); UNITY_END(); }
void loop() {}
```

```bash
pio test -e esp32dev        # builds, flashes, runs, parses PASS/FAIL/IGNORE
```

Real assertion counts, not string-matching. Use this whenever the behaviour is
testable — it is the most deterministic gate and needs no MCP.

### 2. Serial-assert gate — for boot/behaviour markers

When a full test isn't warranted, the firmware prints a success marker and the
gate asserts on it. Two ways:

- **platformio-mcp**: `agent_flash_monitor_verify --expect-all BOOT_OK
  --reject-patterns "Guru Meditation,Brownout detector,WDT reset" --timeout 45`.
- **`scripts/serial_verify.py`** (our own, pyserial-based fallback — no MCP
  dependency): flashes are done separately (`pio run -t upload`), then
  `serial_verify.py --port <p> --baud 115200 --expect BOOT_OK --reject "Guru
  Meditation,Brownout,WDT reset" --timeout 45` opens the port, and exits non-zero
  if the expect marker never appears or any reject pattern does. This is the
  deterministic gate that survives platformio-mcp being young/absent.

Make the firmware print a clear, unique marker (`Serial.println("BOOT_OK");`)
*after* its init actually succeeds — never at the top of `setup()` before the
thing it's asserting has happened.

## The rule

A clean `pio run -t upload` is **not** success. Success is the gate: `pio test`
green, or the serial marker asserted with no crash signature. A flash reported
"done" without the gate is exactly the silent failure this branch refuses to
commit.
