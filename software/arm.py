import argparse
import json
import socket
import subprocess
import time
from pathlib import Path

# 500us = 0 degrees, 2500us = 180 degrees. if a joint doesnt reach its full swing or buzzes at the ends, tweak these
PULSE_MIN, PULSE_MAX = 500, 2500
PERIOD_NS = 20_000_000                                    # 50hz servo signal
JOINTS = {"yaw": 0, "shoulder": 1, "elbow": 2}            # pwm channel: GPIO 12, 13, 18
CENTRE = {"yaw": 90.0, "shoulder": 90.0, "elbow": 90.0}   # servo angle when that joint is at 0 (arm straight up, facing forward)
LIMIT = 85.0                                              # stay a little inside the servos' 180 degrees
MAX_SPEED = 200.0                                         # degrees per second
TIMEOUT = 1.5                                             # seconds without messages before it drifts home


class SysfsPWM:
    """Pi 5 hardware pwm. needs dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4 in /boot/firmware/config.txt"""

    def __init__(self):
        chips = [c for c in Path("/sys/class/pwm").glob("pwmchip*") if (c / "npwm").read_text().strip() == "4"]
        if not chips:
            raise SystemExit("no pwm chip found. add this to /boot/firmware/config.txt and reboot:\n"
                             "dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4")
        self.chip = chips[0]
        # the overlay only sets up 12 and 13, so switch GPIO 18 to its pwm function (channel 2) by hand
        subprocess.run(["pinctrl", "set", "18", "a3"], check=True)
        for ch in JOINTS.values():
            pwm = self.chip / f"pwm{ch}"
            if not pwm.exists():
                (self.chip / "export").write_text(str(ch))
                time.sleep(0.2)  # udev needs a moment to make the files
            (pwm / "period").write_text(str(PERIOD_NS))
            (pwm / "enable").write_text("1")

    def write(self, joint: str, angle: float):
        us = PULSE_MIN + (PULSE_MAX - PULSE_MIN) * angle / 180
        (self.chip / f"pwm{JOINTS[joint]}" / "duty_cycle").write_text(str(int(us * 1000)))

    def off(self):
        for ch in JOINTS.values():
            (self.chip / f"pwm{ch}" / "enable").write_text("0")


class PrintPWM:
    """--dry: print angles instead of moving anything."""

    def __init__(self):
        self.last, self.now = 0.0, {}

    def write(self, joint: str, angle: float):
        self.now[joint] = angle
        if joint == "elbow" and time.time() - self.last > 0.25:
            self.last = time.time()
            print("   ".join(f"{j} {a:6.1f}" for j, a in self.now.items()))

    def off(self):
        pass


def main():
    ap = argparse.ArgumentParser(description="receive joint angles over wifi and move the servos")
    ap.add_argument("--port", type=int, default=5005)
    ap.add_argument("--dry", action="store_true", help="print instead of driving servos")
    args = ap.parse_args()

    pwm = PrintPWM() if args.dry else SysfsPWM()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", args.port))
    sock.setblocking(False)

    target = {j: 0.0 for j in JOINTS}
    pos = {j: 0.0 for j in JOINTS}
    last_msg, tick = 0.0, time.monotonic()
    print(f"listening on udp {args.port}")
    try:
        while True:
            while True:
                try:
                    data, _ = sock.recvfrom(1024)
                except BlockingIOError:
                    break
                msg = json.loads(data)
                if "pan" in msg:  # the head tracker calls the base "pan"
                    msg["yaw"] = msg["pan"]
                last_msg = time.monotonic()
                for j in JOINTS:
                    if j in msg:
                        target[j] = max(-LIMIT, min(LIMIT, float(msg[j])))
            if time.monotonic() - last_msg > TIMEOUT:
                target = {j: 0.0 for j in JOINTS}

            now = time.monotonic()
            step, tick = MAX_SPEED * (now - tick), now
            for j in JOINTS:
                pos[j] += max(-step, min(step, target[j] - pos[j]))
                pwm.write(j, CENTRE[j] + pos[j])
            time.sleep(0.01)
    except KeyboardInterrupt:
        pass
    finally:
        pwm.off()


if __name__ == "__main__":
    main()
