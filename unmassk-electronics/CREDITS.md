# Credits

`unmassk-electronics`'s method and references are original, but the plugin drives
open-source tools it did not write. It stands on:

## Microcontroller branch

- **PlatformIO Core** (Apache-2.0) — https://github.com/platformio/platformio-core
  — the build/flash/`pio test` engine.
- **platformio-mcp** (jl-codes, MIT) — https://github.com/jl-codes/platformio-mcp
  — the agent-first MCP driver with the `agent_flash_monitor_verify` serial gate.
- **embedded-debugger-mcp** (MIT, probe-rs-based) —
  https://github.com/Adancurusul/embedded-debugger-mcp — register/breakpoint debug.
- **esptool** (GPL-2.0) — https://github.com/espressif/esptool — the ESP32 flash
  substrate PlatformIO wraps.
- **ESP-IDF docs** (Apache-2.0) — Espressif's Fatal Errors + IDF Monitor guides,
  the basis for the crash-triage reference.

## Raspberry Pi branch

- **gpiozero** (BSD-3-Clause) — https://github.com/gpiozero/gpiozero — the
  officially recommended GPIO library.
- **pinctrl** (part of raspberrypi/utils) — https://github.com/raspberrypi/utils
  — the independent GPIO read-back tool the gate uses.
- **picamera2** (BSD-2-Clause) — https://github.com/raspberrypi/picamera2 — the
  libcamera-based camera stack.
- **ssh-mcp** (tufantunc, MIT) — https://github.com/tufantunc/ssh-mcp — optional
  structured SSH exec.

## Robotics branch

- **Adafruit CircuitPython** libraries (MIT) — `adafruit-circuitpython-servokit`,
  `adafruit_motor` — https://github.com/adafruit — the cross-board actuator stack.
- **FastAccelStepper** (MIT) — https://github.com/gin66/FastAccelStepper — ESP32
  stepper control.
- Sensor drivers: VL53L0X, HC-SR04, MPU6050 community libraries.
- **ros-mcp-server** (robotmcp, Apache-2.0) — https://github.com/robotmcp/ros-mcp-server
  — noted for the future ROS2 path, not a current dependency.

## Entry kits (referenced, not bundled)

- **SunFounder PiCar-X**, **Freenove 4WD Smart Car Kit** — beginner robot
  platforms that exercise the driver/sensor stack above.

## This plugin

`unmassk-electronics`'s own text (the method, the gate discipline, the references,
the scripts) is licensed MIT — see `LICENSE`.
