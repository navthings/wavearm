# wavearm

a little desk robot arm that copies whatever my arm is doing. i wave, it waves back.

![renders](print/sheet.png)

it started as a two joint thing that could only wave. then i found an old raspberry pi 5 in a drawer and it turned into a proper three joint arm: the base spins, and the shoulder and elbow tilt. the pi hides in the base and moves the servos, and my macbook webcam does the watching. it finds my shoulder, elbow and wrist, works out the angles, and sends them to the pi over wifi.

the whole thing is about $40 of parts plus a lot of light grey PLA.

## how it works

```
mac webcam -> mediapipe finds my arm -> shoulder + elbow angles -> wifi -> pi 5 -> three servos
```

the design is all code (`arm3.py`, using cadquery), so every size is a number at the top of the file. change one, run it again and you get new print files. `check3.py` swings both joints through their whole range and makes sure nothing crashes into anything.

it can also do head tracking (`software/track.py`), where the base just turns to look at you. more on the software in [software/README.md](software/README.md).

## what you need

| part | where | price |
|---|---|---|
| 1x MG90S metal gear servo (shoulder, it holds the whole arm up) | [altronics Z6444](https://www.altronics.com.au/product/z6444-mg90s-metal-geared-micro-servo) | $13.95 |
| 2x 9g plastic servo (base and elbow, barely any load) | altronics Z6392 | $9.95 each |
| jumper wires, pin to socket | altronics P1021 | $4.00 |
| M3x10 screws, 25 pack (it uses 12) | altronics H3120A | $2.60 |
| raspberry pi 5 + the official 27W power supply | had one | |
| microSD card, 16 to 32gb | kmart / officeworks, not altronics (theyre $50+ there lol) | ~$10 |

no soldering, and no tiny M2.5 screws because the pi just sits on printed pegs.

## printing

i print on a bambu a1 mini, so everything is laid out on plates in `print/a1mini/`. 0.2mm layers, 3 walls, 15% gyroid, no supports on anything.

print `plate0_servo_gauge` first. its a strip of slots in slightly different sizes. push each servo into them and the tightest slot it fits is its real size, so you dont need calipers. put those numbers into `arm3.py` before printing plates 2 to 4, since those have the servo pockets.

| plate | whats on it |
|---|---|
| plate1_tray_plus | the base the pi lives in (25% infill so its heavy), plus the servo cover and elbow cap |
| plate2_drum | middle band of the base, holds the base servo |
| plate3_shoulder | the spinning platter and shoulder tower |
| plate4_arm | both arm pieces. turn brim on, the forearm has a tall thin bit |
| plate5_small | light ring, cover, both caps. pause at 1.6mm to swap colour for the logo |

the loose STLs and STEP files (for fusion / onshape) are in `print/` too.

## wiring

| servo | signal | 5V | GND |
|---|---|---|---|
| base | pin 32 (GPIO 12) | pin 2 | pin 6 |
| shoulder | pin 33 (GPIO 13) | pin 4 | pin 14 |
| elbow | pin 12 (GPIO 18) | shares pin 2 or 4 | pin 9 |

the pi only has two 5V pins, so the elbow shares one. strip two jumper wires, twist them together, tape it.

## putting it together

1. centre all three servos at 90 degrees before any horns go on, otherwise it waves lopsided
2. pi onto the pegs in the tray, usb-c lined up with the hole at the back
3. base servo into the drum, drum onto the tray (4 screws from underneath)
4. ring into the drum, horn into the bottom of the platter, platter onto the servo, screw it down through the little hole in the top of the tower
5. shoulder servo slides into the tower from the back, cover clamps it in
6. elbow servo goes inside the top of the upper arm, then the back plate screws on
7. forearm onto the elbow, back plate on, pivot screws snug but not tight
8. press the caps in

## older stuff

`v1/` has the first version, the two joint waving arm. kept it because the three joint one grew out of it.
