import time

import cv2

# asks macos for camera access for whatever terminal runs this, then waits for you to click allow
for i in range(40):
    cap = cv2.VideoCapture(0)
    if cap.isOpened() and cap.read()[0]:
        print("camera works in this terminal. you can close this window.")
        break
    if i == 0:
        print("asking for camera access, click allow on the popup...")
    time.sleep(1)
else:
    print("still blocked. open system settings > privacy & security > camera and turn ghostty on")
time.sleep(600)
