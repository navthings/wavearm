import argparse
import json
import math
import socket
import time
import urllib.request
from pathlib import Path

import cv2

HERE = Path(__file__).parent
MODEL = HERE / "face_detection_yunet_2023mar.onnx"
MODEL_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
CALIB = HERE / "calibration.json"

# the arm sits next to the laptop, so these line its view up with the webcam's
DEFAULTS = {"offset": 0.0, "gain": 1.0, "flip": False, "hfov": 65.0, "lean_gain": 1.2, "lean_flip": False}
PAN_LIMIT, LEAN_LIMIT = 80.0, 45.0
SMOOTH = 0.25           # 0 = frozen, 1 = no smoothing
WAVE_AFTER_AWAY = 3.0   # seconds without a face before it waves hello again


def load_calib() -> dict:
    if CALIB.exists():
        return {**DEFAULTS, **json.loads(CALIB.read_text())}
    return dict(DEFAULTS)


def head_to_angles(face, width: int, cal: dict) -> tuple[float, float]:
    """Face box + eye landmarks from yunet -> (pan, lean) in degrees, 0 = centred."""
    x, y, w, h = face[:4]
    u = ((x + w / 2) / width - 0.5) * 2  # -1 left edge of the image, +1 right edge
    if cal["flip"]:
        u = -u
    pan = cal["offset"] + cal["gain"] * u * cal["hfov"] / 2
    rx, ry, lx, ly = face[4:8]           # right eye, left eye (as yunet names them)
    roll = math.degrees(math.atan2(ly - ry, lx - rx))
    lean = (roll if cal["lean_flip"] else -roll) * cal["lean_gain"]
    clamp = lambda v, lim: max(-lim, min(lim, v))
    return float(clamp(pan, PAN_LIMIT)), float(clamp(lean, LEAN_LIMIT))


def main():
    ap = argparse.ArgumentParser(description="track your head with the mac webcam, send angles to the pi")
    ap.add_argument("--pi", default="raspberrypi.local", help="pi hostname or ip")
    ap.add_argument("--port", type=int, default=5005)
    ap.add_argument("--camera", type=int, default=0)
    args = ap.parse_args()

    if not MODEL.exists():
        print("downloading the face model (230kb, once)...")
        urllib.request.urlretrieve(MODEL_URL, MODEL)
    cap = cv2.VideoCapture(args.camera)
    waited = 0
    while not cap.isOpened() and waited < 30:
        # opencv asks macos for permission then gives up straight away, so keep retrying while the popup is up
        if waited == 0:
            print("waiting for camera permission, click allow on the popup...")
        time.sleep(1)
        waited += 1
        cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise SystemExit("still no camera. run this from apple terminal instead, or check system settings > privacy > camera")
    ok, frame = cap.read()
    if not ok:
        raise SystemExit("webcam opened but gave no frame")
    height, width = frame.shape[:2]
    detector = cv2.FaceDetectorYN.create(str(MODEL), "", (width, height), score_threshold=0.8)

    addr = (socket.gethostbyname(args.pi), args.port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    cal = load_calib()
    pan = lean = 0.0
    last_seen = 0.0
    print(f"sending to {addr[0]}:{addr[1]}. keys: left/right = offset, up/down = gain, f = flip pan, l = flip lean, w = wave, s = save, q = quit")

    while True:
        ok, frame = cap.read()
        if not ok:
            raise SystemExit("lost the webcam")
        _, faces = detector.detect(frame)
        msg = {"t": time.time()}
        if faces is not None and len(faces):
            face = max(faces, key=lambda f: f[2] * f[3])  # biggest face = closest person
            target_pan, target_lean = head_to_angles(face, width, cal)
            pan += SMOOTH * (target_pan - pan)
            lean += SMOOTH * (target_lean - lean)
            if time.time() - last_seen > WAVE_AFTER_AWAY:
                msg["wave"] = True
            last_seen = time.time()
            msg.update(pan=round(pan, 1), lean=round(lean, 1))
            x, y, w, h = map(int, face[:4])
            cv2.rectangle(frame, (x, y), (x + w, y + h), (80, 200, 120), 2)
        sock.sendto(json.dumps(msg).encode(), addr)

        status = f"pan {pan:+.0f}  lean {lean:+.0f}  offset {cal['offset']:+.0f}  gain {cal['gain']:.2f}  flip {cal['flip']}"
        cv2.putText(frame, status, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.imshow("wave arm", frame)
        key = cv2.waitKeyEx(1)
        if key in (ord("q"), 27):
            break
        elif key in (2, 63234, 65361):    # left arrow (mac / linux codes)
            cal["offset"] -= 2
        elif key in (3, 63235, 65363):    # right arrow
            cal["offset"] += 2
        elif key in (0, 63232, 65362):    # up arrow
            cal["gain"] = round(cal["gain"] + 0.05, 2)
        elif key in (1, 63233, 65364):    # down arrow
            cal["gain"] = round(max(0.1, cal["gain"] - 0.05), 2)
        elif key == ord("f"):
            cal["flip"] = not cal["flip"]
        elif key == ord("l"):
            cal["lean_flip"] = not cal["lean_flip"]
        elif key == ord("w"):
            sock.sendto(json.dumps({"t": time.time(), "wave": True}).encode(), addr)
        elif key == ord("s"):
            CALIB.write_text(json.dumps(cal, indent=2))
            print("saved", CALIB)

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
