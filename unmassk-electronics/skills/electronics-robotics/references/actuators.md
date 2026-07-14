# Actuators — servos, DC motors, steppers

Read before writing motion code. The library choice that matters: **Adafruit
CircuitPython runs the same API on ESP32 (native) and Raspberry Pi (via Blinka)**
— write the motion logic once, run it on either lower branch.

## Servos — PCA9685 (16-channel PWM)

```python
from adafruit_servokit import ServoKit
kit = ServoKit(channels=16)          # I2C, default 0x40
kit.servo[0].angle = 90              # centre
```

- Install: `pip3 install adafruit-circuitpython-servokit` (Pi via Blinka;
  ESP32/RP2040 run CircuitPython natively).
- On ESP32 with Arduino/C++: `Adafruit-PWM-Servo-Driver-Library` (same chip).
- **Do not** use the archived `Adafruit_Python_PCA9685`.
- **Servo centres/dead-zones are calibrated by hand** — `angle = 90` is nominal;
  the real centre is per-servo and set physically. This is a human step.

## DC motors — L298N / TB6612

```python
from adafruit_motor import motor
# or, pure-Pi GPIO without CircuitPython:
from gpiozero import Motor
m = Motor(forward=17, backward=18)   # BCM pins
m.forward(0.6)                       # 60% PWM
```

- **TB6612** is electrically cleaner than L298N (lower voltage drop, no
  heatsink) — prefer it for new builds; both drive the same way in code.
- `gpiozero`'s `Motor` covers a plain L298N directly (raw GPIO+PWM) — no
  third-party wrapper needed on a Pi.

## Steppers — DRV8825 / A4988

- On ESP32/RP2040: **`FastAccelStepper`** (C++) — non-blocking, acceleration
  profiles, high step rates. Prefer over the older `AccelStepper`.
- On Arduino generally: `RobTillaart/DRV8825`.

## The power caveat (hardware, not code)

Motors draw far more than a logic pin can supply, and **stall current** can
exceed a driver's rating. Motor power comes from a separate supply, not the
board's 3V3/5V rail; grounds are common. Whether the chosen driver survives the
motor's stall current is a **hardware sizing decision the agent cannot verify** —
flag it, don't assume it. A brownout/reset on the microcontroller branch during
a motor burst is usually this.

## Composition

This code is authored here but **runs on** the microcontroller branch (flashed
firmware) or the Pi branch (Python process). Movement verification always goes
through `references/sensor-gate.md`.
