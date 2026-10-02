# software

your mac webcam watches you, works out where the robot should point, and sends that to the pi over wifi. the pi just moves the servos.

- `armtrack.py` (mac): copies your arm. your shoulder and elbow angles go straight to the robots shoulder and elbow
- `track.py` (mac): head tracking, the base turns to face you
- `arm.py` (pi): receives angles and drives the three servos

## on the mac (arm copy)

```zsh
cd ~/Documents/Projects/wavearm/software
source .venv312/bin/activate
python armtrack.py --pi raspberrypi.local
```

`.venv312` is python 3.12 with mediapipe 0.10.14 (the classic cpu pose model, the newer one crashes on macs trying to use metal). it runs about 15ms a frame.

keys: a = switch which arm it copies, s / e = flip shoulder / elbow direction if it moves the wrong way, left/right = turn the base, w = save, q = quit. stand back far enough that your shoulder, elbow and wrist are all in frame.

## on the pi

add this to `/boot/firmware/config.txt` and reboot (hardware pwm on GPIO 12 and 13, arm.py switches GPIO 18 on itself):

```
dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4
```

```zsh
scp arm.py pi@raspberrypi.local:~
ssh pi@raspberrypi.local "sudo python3 arm.py"
```

## wiring (no soldering)

| servo | signal | 5V | GND |
|---|---|---|---|
| base (plastic) | pin 32 (GPIO 12) | pin 2 | pin 6 |
| shoulder (metal MG90S) | pin 33 (GPIO 13) | pin 4 | pin 14 |
| elbow (plastic) | pin 12 (GPIO 18) | shares pin 2 or 4 | pin 9 |

the pi only has two 5V pins, so the elbow shares one: strip 1cm off two jumper wires, twist them together, tape it. use the official 27W pi power supply or the pi will reboot when the servos start.

## testing without the pi

`python3 arm.py --dry` in one window, `python armtrack.py --pi 127.0.0.1` in another. arm.py prints the angles instead of moving anything.

## tuning (top of arm.py)

- `PULSE_MIN` / `PULSE_MAX`: if a joint doesnt reach its full swing or buzzes at the ends
- `CENTRE`: if straight up isnt quite straight, change 90 to 85 or 95 for that joint
- `MAX_SPEED`: lower = calmer, higher = snappier
