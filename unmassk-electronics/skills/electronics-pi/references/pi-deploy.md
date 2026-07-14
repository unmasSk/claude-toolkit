# Deploying a service on a Pi — with a health-check gate

Read before deploying anything long-running (a sensor logger, a camera stream, a
local API). The gate: **a service is "up" only when a health check confirms it**,
not when `systemctl start` returns 0.

## systemd unit with a built-in gate

```ini
# /etc/systemd/system/mything.service
[Unit]
Description=My hardware thing
After=network-online.target

[Service]
ExecStart=/usr/bin/python3 /home/pi/mything/main.py
ExecStartPost=/usr/bin/curl -fsS http://localhost:8000/health   # the gate
Restart=on-failure
User=pi

[Install]
WantedBy=multi-user.target
```

`ExecStartPost` runs after start; if the health curl fails, systemd marks the
unit failed — the health check IS the gate, baked into the unit.

## The deploy loop

```
1. pre-flight   systemd-analyze verify mything.service   (syntax gate)          [agent]
2. deploy       scp / git pull the code to the Pi                               [agent]
3. reload       sudo systemctl daemon-reload && sudo systemctl restart mything  [agent]
4. ⛔GATE        systemctl is-active mything && curl -fsS localhost:8000/health  [agent]
                AND journalctl -u mything -n 20 --no-pager (no errors)
                -> only now is it deployed. is-active alone is not enough — a
                   service can be "active" and looping-restarting.
```

## Docker (optional)

Docker works on a Pi and is common for homelab use, but **check kernel
compatibility first** — an upstream `linux-rpi` kernel reportedly broke Docker
in one release. If used, the gate is the same idea: `docker inspect
--format '{{.State.Health.Status}}' <c>` with a `HEALTHCHECK` in the image, not
just "the container is running".

## Honest limit

A health check confirms the *software* is serving; it can't confirm the *sensor
it reads is wired correctly*. Pair a service health check with the GPIO/sensor
read-back gate (`references/gpio-gate.md`) when the service depends on hardware
input — otherwise a happily-running service can be faithfully reporting garbage
from a disconnected pin.
