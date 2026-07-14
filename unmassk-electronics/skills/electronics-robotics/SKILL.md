---
name: electronics-robotics
description: >
  Use when the user asks to "control a motor / servo / stepper", "build a robot",
  "make a robot car / arm move", "drive an actuator", "use a PCA9685 servo
  driver", "read a sensor to confirm the robot moved", "pan-tilt a camera", or is
  building hobby robotics behaviour on top of a microcontroller or a Raspberry
  Pi. Or mentions any of: robot, robotics, motor, DC motor, servo, stepper,
  actuator, PCA9685, L298N, TB6612, DRV8825, motor driver, encoder, sensor
  feedback, PiCar, robot car, pan-tilt, differential drive.
  Covers the robotics behaviour branch — the layer that sequences motors/servos
  and reads sensors, sitting on top of the microcontroller branch (firmware) and
  the Raspberry Pi branch (Python). The one rule: never report a movement done
  from the command you sent — read a sensor back (distance, IMU delta, encoder
  ticks) after the action and confirm it changed as expected. Also covers the
  recommended cross-branch actuator library (Adafruit CircuitPython, same API on
  ESP32 and Pi) and beginner robot kits.
  Use when NOT: the task is pure firmware (compile/flash a microcontroller with
  no motion) or pure Pi/Linux admin with no actuators — those are the other two
  branches. Not for designing or 3D-printing the chassis.
version: 1.0.0
---

# electronics-robotics — Motors, Servos, Sensors

The behaviour layer. This branch doesn't own its own board — it writes the
motor/servo/sensor code that the **microcontroller** branch flashes or the
**Raspberry Pi** branch runs. What it owns is the discipline that makes a robot
trustworthy: **a movement is not done until a sensor says it happened.**

## THE GATE — sensor feedback, not the command

A servo command that returned is not evidence the servo moved. A motor
`forward()` that didn't error is not evidence the robot advanced. So:

```
1. ACT       send the motor/servo command                              [agent]
2. ⛔GATE: SENSOR READ-BACK   read a sensor AFTER the action and compare to        [agent]
             the expected change:
               - distance (VL53L0X / HC-SR04) dropped/rose as expected?
               - IMU (MPU6050) yaw/accel delta matches the intended turn?
               - encoder tick count matches the intended travel?
             No confirming read → the movement is NOT confirmed, full stop.
```

"Obstacle avoided" / "turned 90°" / "drove forward 20cm" are claims that require
a sensor number, never the fact that the command executed. A silently-wrong
movement reported as success is this branch's self-harm case.

## Actuators — one library across both boards

The **Adafruit CircuitPython** family is the recommended stack because it runs
with the **same API on an ESP32 (CircuitPython native) and a Raspberry Pi (via
Blinka)** — the natural glue between the two lower branches:

| Need | Library |
| --- | --- |
| Servos (PCA9685, 16-ch PWM) | `adafruit-circuitpython-servokit` |
| DC / stepper motors | `adafruit_motor` |
| Steppers on ESP32 (fast, non-blocking) | `FastAccelStepper` (C++) |
| Pure-Pi GPIO motors (no CircuitPython) | `gpiozero` `Motor` class |

Avoid the archived `Adafruit_Python_PCA9685`. TB6612 is electrically cleaner
than L298N (no heatsink); either works, drive them via `adafruit_motor` /
`gpiozero`.

## Sensors — the gate primitives

| Sensor | Reads | Use as gate for |
| --- | --- | --- |
| VL53L0X (ToF, I2C) | precise distance (cm) | "stopped before the wall" |
| HC-SR04 (ultrasonic) | cheap distance | "obstacle detected" |
| MPU6050 (IMU, I2C) | orientation / accel | "turned/tilted the right amount" |
| encoders (GPIO IRQ) | wheel rotation | "drove the intended distance" |

See `references/sensor-gate.md` for the read-back-after-action pattern.

## ROS2? Not day one

For a solo hobbyist starting out (single board, a few sensors, a few hundred
lines of behaviour), **ROS2 is overkill** — its setup cost exceeds the robot's.
Plain Python/firmware is the right start. ROS2 earns its complexity only with
multiple coordinated nodes or when you need RViz/rosbag — a possible *later*
addition, not a dependency now. (If it ever is adopted, `ros-mcp-server` is the
credible MCP integration.)

## Entry kits

Once hardware is bought: **SunFounder PiCar-X** or **Freenove 4WD** (both ship
working Python that exercises exactly this driver/sensor stack on a Pi). A kit
removes the "which driver board do I need" decision — not the soldering iron.

## The honest limit

The agent writes correct driver and behaviour code, and refuses to claim a
movement worked without sensor confirmation. It does **not** wire the motors,
solder the driver board, set the servo centre points by hand, or check that the
motor's stall current fits the driver's rating. There is no "download a finished
robot."

## When to read which reference

- `references/actuators.md` — servo/motor/stepper wiring and library patterns.
- `references/sensor-gate.md` — the read-a-sensor-after-you-move gate, per sensor.
