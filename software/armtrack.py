import argparse
import json
import math
import socket
import time
from pathlib import Path

import cv2
import mediapipe as mp

HERE = Path(__file__).parent
CALIB = HERE / "arm_calibration.json"

# landmark ids: (shoulder, elbow, wrist) for your right and left arm
ARMS = {"right": (12, 14, 16), "left": (11, 13, 15)}
DEFAULTS = {"arm": "right", "yaw": 85.0, "shoulder_sign": 1, "elbow_sign": 1}
LIMIT = 90.0            # every servo does 180 degrees, so +-90 from centre
SMOOTH = 0.3
MIN_VIS = 0.5           # ignore the arm if mediapipe isnt sure it can see it


def load_calib() -> dict:
    return {**DEFAULTS, **json.loads(CALIB.read_text())} if CALIB.exists() else dict(DEFAULTS)


def arm_angles(lm, arm: str, cal: dict):
    """Your shoulder/elbow/wrist in the image -> robot (shoulder, elbow) degrees, or None if not visible."""
    s, e, w = (lm[i] for i in ARMS[arm])
    if min(s.visibility, e.visibility, w.visibility) < MIN_VIS:
        return None
    ux, uy = e.x - s.x, e.y - s.y            # upper arm, image y points down
    fx, fy = w.x - e.x, w.y - e.y            # forearm
    shoulder = math.degrees(math.atan2(ux, -uy))                       # 0 = arm straight up
    elbow = math.degrees(math.atan2(ux * fy - uy * fx, ux * fx + uy * fy))  # 0 = arm straight
    clamp = lambda v: max(-LIMIT, min(LIMIT, v))
    return clamp(shoulder * cal["shoulder_sign"]), clamp(elbow * cal["elbow_sign"])


def main():
    ap = argparse.ArgumentParser(description="copy your arm with the robot arm")
    ap.add_argument("--pi", default="raspberrypi.local")
    ap.add_argument("--port", type=int, default=5005)
    ap.add_argument("--camera", type=int, default=0)
    args = ap.parse_args()

    # the classic cpu pose model (mediapipe 0.10.14). the newer tasks api crashes on some macs trying to use metal
    pose = mp.solutions.pose.Pose(model_complexity=0, min_detection_confidence=0.5, min_tracking_confidence=0.5)

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
        raise SystemExit("no camera. run this from apple terminal, or check system settings > privacy > camera")

    addr = (socket.gethostbyname(args.pi), args.port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    cal = load_calib()
    shoulder = elbow = 0.0
    print(f"sending to {addr[0]}:{addr[1]}. keys: a = switch arm, s/e = flip shoulder/elbow, left/right = turn base, w = save, q = quit")

    while True:
        ok, frame = cap.read()
        if not ok:
            raise SystemExit("lost the webcam")
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = pose.process(rgb)
        msg = {"t": time.time(), "yaw": cal["yaw"]}
        h, w = frame.shape[:2]
        if res.pose_landmarks:
            lm = res.pose_landmarks.landmark
            angles = arm_angles(lm, cal["arm"], cal)
            if angles:
                shoulder += SMOOTH * (angles[0] - shoulder)
                elbow += SMOOTH * (angles[1] - elbow)
                msg.update(shoulder=round(shoulder, 1), elbow=round(elbow, 1))
            pts = [(int(lm[i].x * w), int(lm[i].y * h)) for i in ARMS[cal["arm"]]]
            cv2.line(frame, pts[0], pts[1], (80, 200, 120), 6)
            cv2.line(frame, pts[1], pts[2], (80, 160, 240), 6)
            for p in pts:
                cv2.circle(frame, p, 9, (255, 255, 255), -1)
        sock.sendto(json.dumps(msg).encode(), addr)

        view = cv2.flip(frame, 1)  # mirror the preview so it feels natural
        text = f"{cal['arm']} arm   shoulder {shoulder:+.0f}   elbow {elbow:+.0f}   base {cal['yaw']:+.0f}"
        cv2.putText(view, text, (14, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.imshow("arm copy", view)
        key = cv2.waitKeyEx(1)
        if key in (ord("q"), 27):
            break
        elif key == ord("a"):
            cal["arm"] = "left" if cal["arm"] == "right" else "right"
        elif key == ord("s"):
            cal["shoulder_sign"] *= -1
        elif key == ord("e"):
            cal["elbow_sign"] *= -1
        elif key in (2, 63234, 65361):
            cal["yaw"] = max(-LIMIT, cal["yaw"] - 5)
        elif key in (3, 63235, 65363):
            cal["yaw"] = min(LIMIT, cal["yaw"] + 5)
        elif key == ord("w"):
            CALIB.write_text(json.dumps(cal, indent=2))
            print("saved", CALIB)

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
