# Setup — the START step of a Raspberry Pi project

Run **only when a project is actually a Pi/Linux-SBC project** (START-gated).
The installer is `scripts/setup_pi_env.py`; this is its contract. Most of this
runs **on the Pi** over SSH, not on the dev machine.

## 1. Headless provisioning (before first SSH)

Flash Raspberry Pi OS with **Raspberry Pi Imager** → Advanced Options (gear
icon): enable SSH, set the Wi-Fi + user + hostname. No monitor needed. First
boot brings the Pi up on the network reachable by `ssh <user>@<host>.local`.

## 2. On the Pi (over SSH)

```bash
sudo apt update
sudo apt install -y python3-gpiozero python3-picamera2 pinctrl
python3 -m pip install --user smbus2 spidev pyserial   # I2C/SPI/serial
```

- **gpiozero** — the officially recommended GPIO library (all models). Do NOT
  install `RPi.GPIO` for new work: deprecated and broken on Pi 5 (RP1 chip).
- **picamera2** via `apt` (not `pip`) so it stays matched to the system
  libcamera.
- **pinctrl** — the CLI read-back tool the gate uses.

## 3. Permissions (report, don't assume)

Serial/GPIO access needs group membership:

```bash
sudo usermod -aG dialout,gpio,i2c,spi $USER   # then log out / back in
```

## 4. Verify (don't trust, check)

```bash
python3 -c "import gpiozero; print('gpiozero', gpiozero.__version__)"
pinctrl -h >/dev/null && echo "pinctrl OK"
```

## 5. Known gotcha to record in the per-device profile

`lgpio` (gpiozero's Pi-5 backend) has a reported pin-factory bug on **kernel
6.6.45** that can silently misread pins. Record the Pi's kernel version
(`uname -r`) in the per-device profile; if it matches, cross-check every GPIO
read against `pinctrl get` and flag the risk. A library that lies about pin
state is exactly the self-harm case the gate exists to catch.

## 6. Optional

- **Hailo AI Kit** (`sudo apt install hailo-all`) — only if real-time on-device
  AI is the goal. OpenCV (`python3-opencv`) for basic CV.
- **Docker** — common for homelab Pi use; check kernel compatibility first (an
  upstream `linux-rpi` kernel reportedly broke Docker in one release).
