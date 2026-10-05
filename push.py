"""
push_camera.py - run this on the laptop that has the USB camera.

It reads the camera with OpenCV and POSTs JPEG frames to the Render backend
(/api/camera/push). The backend must have:
    VIDEO_SOURCE=push
    CAMERA_PUSH_KEY=<same secret you put below>

Install once:   pip install opencv-python requests
Run:            python push_camera.py
Optional env:   SERVER, CAMERA_PUSH_KEY, CAM_INDEX, FPS
"""
import os
import sys
import time

import cv2
import requests

SERVER = os.environ.get("SERVER", "https://jan-suraksha.onrender.com").rstrip("/")
KEY = os.environ.get("push", "Jzz3BAlCqPEK9tTqzyfbFJxLNop21lX76lkL2DqDdSM")
CAM_INDEX = int(os.environ.get("CAM_INDEX", "0"))
FPS = float(os.environ.get("FPS", "8"))
JPEG_QUALITY = 60
URL = SERVER + "/api/camera/push"


def open_camera():
    # DSHOW is the reliable backend on Windows; fall back to the default elsewhere.
    for backend in (cv2.CAP_DSHOW, cv2.CAP_ANY):
        cap = cv2.VideoCapture(CAM_INDEX, backend)
        if cap.isOpened():
            ok, _ = cap.read()
            if ok:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                return cap
        cap.release()
    return None


def main():
    if KEY == "PUT_YOUR_SECRET_KEY_HERE":
        print("Set CAMERA_PUSH_KEY (env var) or edit KEY in this file.")
        sys.exit(1)

    cap = open_camera()
    if cap is None:
        print(f"Could not open camera index {CAM_INDEX}. Close other apps using it, "
              f"or try CAM_INDEX=1.")
        sys.exit(1)
    print(f"Camera {CAM_INDEX} open. Pushing to {URL} at ~{FPS:g} fps. Ctrl+C to stop.")

    session = requests.Session()
    headers = {"X-Camera-Key": KEY, "Content-Type": "image/jpeg"}
    interval = 1.0 / FPS
    sent = failures = 0
    last_log = time.time()

    try:
        while True:
            t0 = time.time()
            ok, frame = cap.read()
            if not ok or frame is None:
                print("Camera read failed, retrying...")
                cap.release()
                time.sleep(1)
                cap = open_camera()
                if cap is None:
                    time.sleep(3)
                continue

            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            if ok:
                try:
                    r = session.post(URL, data=buf.tobytes(), headers=headers, timeout=10)
                    if r.status_code == 200:
                        sent += 1
                    else:
                        failures += 1
                        print(f"Server replied {r.status_code}: {r.text[:120]}")
                        if r.status_code in (401, 409, 503):
                            time.sleep(3)   # config problem; don't hammer the server
                except requests.RequestException as e:
                    failures += 1
                    print(f"Push failed: {e}")
                    time.sleep(2)           # Render may be waking from sleep

            if time.time() - last_log >= 10:
                print(f"sent={sent} failed={failures}")
                last_log = time.time()

            time.sleep(max(0.0, interval - (time.time() - t0)))
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()


if __name__ == "__main__":
    main()
