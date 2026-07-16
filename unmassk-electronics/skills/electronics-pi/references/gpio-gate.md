# The GPIO gate — write with one path, verify with another

Read before driving pins. The rule: **never trust a single library's own report
of pin state.** A write can silently fail (wrong backend, kernel bug, wrong pin
number), and the library will happily tell you it worked.

## Write with gpiozero

```python
from gpiozero import LED
led = LED(17)          # BCM numbering
led.on()
```

gpiozero auto-selects the backend (`lgpio` on Pi 5, `RPi.GPIO`/others on older
models). Clean, Pythonic, officially recommended.

## Verify with pinctrl (the second path)

```bash
pinctrl get 17
# -> 17: op dh pd | hi  ->  output, driving high  ==  led.on() confirmed
```

`pinctrl` reads the hardware register directly, independent of gpiozero's
backend. If gpiozero says "on" but `pinctrl get` says the pin is low, **the gate
fails** — the write did not take, and you must not report the action done.

## The gate pattern

```
set pin (gpiozero)  ->  pinctrl get <pin>  ->  compare to intended state
                                            ->  match? done. mismatch? FAIL loudly.
```

For an **input** (a sensor/button), read it through gpiozero AND sanity-check
against `pinctrl get` when a reading looks wrong before trusting it.

## The lgpio / kernel gotcha

There is an open issue where the `lgpio` pin factory misreads pins on Pi 5 with
**kernel 6.6.45**. This is precisely why the gate reads back through `pinctrl`
rather than trusting gpiozero alone. Record the kernel version (`uname -r`) as
a `memo(device/<id>)` (objective profile); on an affected kernel, treat every
gpiozero read as suspect until `pinctrl` confirms it.

## Honest limit

`pinctrl` confirms the *pin's electrical state*, not that the *wire is connected
to the thing you think*. A pin can read high correctly while the LED stays dark
because the jumper is in the wrong hole. The gate catches software/driver lies;
it cannot see the breadboard.
