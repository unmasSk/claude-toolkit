# The sensor gate — read after you move

Read before claiming any movement worked. The rule restated: **the command you
sent is not evidence; a sensor reading after the action is.**

## The pattern

```
before = read_sensor()          # baseline
actuate()                       # move / turn / drive
sleep(settling_time)            # let the physical world catch up
after = read_sensor()           # the truth
assert expected_change(before, after)   # gate: matched? done. else FAIL.
```

Never collapse this to "I sent `forward()`, so it moved." The `sleep` matters —
the physical world lags the command; reading too early reads the old state.

## Per-sensor gates

**VL53L0X (ToF, I2C) — precise distance**
```python
# distance dropped as the robot approached the wall?
assert after_mm < before_mm - 30   # moved ≥3cm closer
```
Best for "stopped before the wall" / close-range positioning (cm precision).

**HC-SR04 (ultrasonic) — cheap distance**
Trigger/echo pulse timing over two GPIO pins. Coarser than ToF; fine for
"obstacle present / gone". Note: ultrasonic is noisy — take a median of a few
reads before asserting.

**MPU6050 (IMU, I2C) — orientation / motion**
```python
# turned ~90°? integrate gyro yaw, or compare heading delta
assert abs(yaw_after - yaw_before - 90) < 10   # within tolerance
```
The gate for "turned N degrees" / "is it tilting". Gyro drifts — compare deltas
over short windows, not absolute heading over minutes.

## Tolerances, not equality

Physical motion never lands exactly — gate on a **range**, not `==`. "Drove
20cm" passes at 18–22cm; "turned 90°" passes at 80–100°. Too tight a tolerance
fails on normal slop; too loose passes a real miss. Pick the band from what the
task actually needs.

## When there's no sensor

If a movement genuinely can't be sensor-confirmed (no encoder, no IMU), say so
plainly — **do not upgrade "command sent" to "movement confirmed"**. Report it as
*commanded, unverified*, and recommend the sensor that would close the gate.
That honesty is the whole point: an unverifiable claim stated as verified is the
failure this branch exists to prevent.
