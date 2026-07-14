# ESP32 crash triage

Read when a board crashes, reboots in a loop, or the serial-assert gate trips on
a crash signature. These are the ESP32 failure modes the gate's `--reject-patterns`
should catch, and how to diagnose each. Sourced from Espressif's official docs
(date-check them — they move): ESP-IDF *Fatal Errors* guide and *IDF Monitor*.

## The backtrace is already decoded — use it

`idf.py monitor` (and PlatformIO's monitor with the esp32 exception decoder
filter) **automatically decodes** the crash backtrace hex addresses to
`file:line` against the project's ELF via `addr2line`. So the gate doesn't parse
raw hex — it greps the decoded output. Always read the decoded backtrace before
guessing.

## The crash signatures (what the gate rejects)

| Signature in serial | Means | Usual cause |
| --- | --- | --- |
| **Guru Meditation Error** (`LoadProhibited` / `StoreProhibited`) | CPU exception — bad memory access | null / dangling pointer, use-after-free, array overrun |
| **Guru Meditation** (`IllegalInstruction`) | jumped into non-code | corrupted function pointer, stack smash |
| **Stack canary watchpoint / stack overflow** | a task blew its stack | task stack too small, deep recursion, big local buffers |
| **Brownout detector was triggered** | supply voltage dipped | weak USB power, motor/WiFi current spike, thin wires |
| **Task watchdog got triggered (WDT)** | a task hogged the CPU | blocking loop, `delay()` in a callback, no `yield`/`vTaskDelay` |
| **rst:0x... (RTCWDT_RTC_RESET)** boot loop | reset before app start | bad partition, corrupt flash, brownout at boot |

## Diagnosis loop

1. Read the **decoded backtrace** — top frame is where it died.
2. Match the signature above to narrow the class.
3. For memory faults: inspect the pointer/array at that `file:line`.
4. For **brownout**: suspect power before code — a motor or WiFi burst on thin
   USB power is the classic; add a capacitor / better supply / thicker wires.
   This is a *hardware* cause the code can't fix.
5. For **WDT**: find the blocking section; break it up or feed the watchdog.
6. For **stack overflow**: raise the task stack size, or move big buffers off the
   stack.

## For the deep cases: coredump

When serial-only isn't enough, enable coredump-to-flash and use
`idf.py coredump-info` / `idf.py coredump-debug` for a post-mortem with full
register and stack state. Reserve this for reproducible crashes that the
backtrace alone doesn't explain.

## The honest note

A brownout or a reset loop can be a **wiring/power** problem, not a firmware bug.
The gate correctly refuses to call the flash "done" — but the fix may be at the
breadboard, not in the code. Don't chase a software cause for a hardware
symptom.
