import os
import time
import urllib.request
from collections import deque
from dataclasses import dataclass
from typing import Optional, Tuple, List

import cv2
import numpy as np
import mediapipe as mp


URLS = {
    "hand": "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task",
    "face": "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task",
    "pose": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task",
}

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (0, 9), (9, 10), (10, 11), (11, 12),
    (0, 13), (13, 14), (14, 15), (15, 16),
    (0, 17), (17, 18), (18, 19), (19, 20),
    (5, 9), (9, 13), (13, 17),
]

POSE_CONNECTIONS = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (11, 23), (12, 24), (23, 24), (23, 25), (25, 27),
    (24, 26), (26, 28), (27, 31), (28, 32), (25, 26),
]


@dataclass
class DetectionResult:
    """ Obiekt który dostaniesz po każdej detekcji """
    hands: List = None
    left_hand: List = None
    right_hand: List = None
    left_fist: bool = False
    right_fist: bool = False
    left_palm: Optional[Tuple[float, float]] = None
    right_palm: Optional[Tuple[float, float]] = None
    faces: List = None
    pose: List = None
    fps: int = 0


def cache_dir():
    base = os.getenv("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".cache")
    p = os.path.join(base, "MediaPipeModels")
    os.makedirs(p, exist_ok=True)
    return p


def ensure_model(name: str) -> str:
    p = os.path.join(cache_dir(), f"{name}.task")
    if not os.path.isfile(p):
        print(f"⬇️  Pobieram model: {name}")
        tmp = p + ".tmp"
        urllib.request.urlretrieve(URLS[name], tmp)
        os.replace(tmp, p)
    return p


class Detector:
    def __init__(self,
                 camera_id: int = 0,
                 resolution: Tuple[int, int] = (1280, 720),
                 hands: bool = True,
                 face: bool = False,
                 pose: bool = False,
                 draw: bool = True):

        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision

        self.draw = draw
        self.show_angles = True
        self.mode = "hands"

        self.hand_detector = None
        self.face_detector = None
        self.pose_detector = None

        if hands:
            hand_path = ensure_model("hand")
            self.hand_detector = vision.HandLandmarker.create_from_options(
                vision.HandLandmarkerOptions(
                    base_options=python.BaseOptions(model_asset_path=hand_path),
                    num_hands=2,
                    min_hand_detection_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
            )

        if face:
            face_path = ensure_model("face")
            self.face_detector = vision.FaceLandmarker.create_from_options(
                vision.FaceLandmarkerOptions(
                    base_options=python.BaseOptions(model_asset_path=face_path),
                    num_faces=2,
                    min_face_detection_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
            )

        if pose:
            pose_path = ensure_model("pose")
            self.pose_detector = vision.PoseLandmarker.create_from_options(
                vision.PoseLandmarkerOptions(
                    base_options=python.BaseOptions(model_asset_path=pose_path),
                    num_poses=2,
                    min_pose_detection_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
            )

        self.cap = cv2.VideoCapture(camera_id)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])

        self.fps_hist = deque(maxlen=30)
        self._prev_time = time.time()
        self.frame = None

        print("✅ Detektor gotowy")

    # --- Narzędzia matematyczne ---
    @staticmethod
    def v3(lm):
        return np.array([lm.x, lm.y, lm.z], dtype=np.float32)

    @staticmethod
    def unit(v):
        n = float(np.linalg.norm(v))
        return v / n if n > 1e-6 else v

    @staticmethod
    def angle_deg(a, b):
        c = float(np.clip(np.dot(Detector.unit(a), Detector.unit(b)), -1.0, 1.0))
        return float(np.degrees(np.arccos(c)))

    @staticmethod
    def is_fist(lms) -> bool:
        idxs = [0, 5, 9, 13, 17]
        pts = [Detector.v3(lms[i]) for i in idxs]
        palm = sum(pts) / len(pts)
        tips = [4, 8, 12, 16, 20]
        span = float(np.linalg.norm(Detector.v3(lms[0]) - Detector.v3(lms[9])))
        if span < 1e-6:
            return False

        dists = [float(np.linalg.norm(Detector.v3(lms[t]) - palm)) for t in tips]
        thresh = 0.4 * span
        fingers_folded = all(d < thresh for d in dists[1:])

        thumb_tip = Detector.v3(lms[4])
        thumb_mcp = Detector.v3(lms[2])
        thumb_dir = thumb_tip - thumb_mcp
        index_mcp = Detector.v3(lms[5])

        dist_thumb_palm = float(np.linalg.norm(thumb_tip - palm))
        dist_thumb_indexbase = float(np.linalg.norm(thumb_tip - index_mcp))
        palm_axis = Detector.v3(lms[9]) - Detector.v3(lms[0])
        ang_thumb_palm = Detector.angle_deg(thumb_dir, palm_axis)

        thumb_close = dist_thumb_palm < (0.35 * span)
        thumb_tucked = dist_thumb_indexbase < (0.28 * span)
        thumb_across = ang_thumb_palm > 100.0
        thumb_folded = thumb_close or thumb_tucked or thumb_across

        return fingers_folded and thumb_folded

    @staticmethod
    def palm_center_norm(lms):
        idxs = [0, 5, 9, 13, 17]
        pts = [Detector.v3(lms[i]) for i in idxs]
        palm = sum(pts) / len(pts)
        return float(palm[0]), float(palm[1])

    # --- Główna metoda detekcji ---
    def update(self) -> DetectionResult:
        ok, frame = self.cap.read()
        if not ok:
            return DetectionResult()

        self.frame = cv2.flip(frame, 1)
        h, w = self.frame.shape[:2]
        res = DetectionResult()

        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(self.frame, cv2.COLOR_BGR2RGB))

        if self.hand_detector:
            det = self.hand_detector.detect(mp_image)
            res.hands = det.hand_landmarks
            res.left_fist = res.right_fist = False

            for idx, hand in enumerate(res.hands):
                handedness = det.handedness[idx][0].category_name

                if self.draw:
                    for a, b in HAND_CONNECTIONS:
                        s = hand[a]
                        e = hand[b]
                        cv2.line(self.frame, (int(s.x * w), int(s.y * h)), (int(e.x * w), int(e.y * h)), (0, 255, 0), 2)
                    for lm in hand:
                        cv2.circle(self.frame, (int(lm.x * w), int(lm.y * h)), 4, (0, 0, 255), -1)

                fist = self.is_fist(hand)
                palm = self.palm_center_norm(hand)

                if handedness == "Left":
                    res.left_hand = hand
                    res.left_fist = fist
                    res.left_palm = palm
                else:
                    res.right_hand = hand
                    res.right_fist = fist
                    res.right_palm = palm

        # Oblicz FPS
        now = time.time()
        dt = now - self._prev_time
        self._prev_time = now
        res.fps = int(1 / dt) if dt > 1e-6 else 0

        return res

    def show(self) -> bool:
        """ Wyświetla okno, zwraca True jeśli użytkownik nacisnął Q aby wyjść """
        cv2.imshow("Detector", self.frame)
        k = cv2.waitKey(1) & 0xFF
        if k == ord("q"):
            self.close()
            return True
        return False

    def close(self):
        self.cap.release()
        cv2.destroyAllWindows()

    def run(self):
        """ Domyślna pętla, działa tak samo jak oryginalny kod """
        while True:
            r = self.update()
            print(f"Prawa pięść: {r.right_fist} Lewa pięść: {r.left_fist} Pozycja: {r.right_palm}")
            if self.show():
                break


if __name__ == "__main__":
    Detector().run()