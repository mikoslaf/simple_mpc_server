"""
Główna klasa GestureTracker – łączy kamerę, detekcję i analizę.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional, Generator, Tuple

import cv2
import numpy as np
import mediapipe as mp

from .models import ensure_model
from .camera import Camera, CameraConfig
from .analysis import HandAnalyzer, HandAngles
from . import drawing


# ── Wyniki detekcji (czyste dane) ────────────────────────


@dataclass
class HandResult:
    """Wynik detekcji jednej dłoni."""
    landmarks: list
    """Surowe landmarki MediaPipe (21 punktów)."""
    is_fist: bool
    """Czy dłoń jest zaciśnięta w pięść."""
    palm_center: Tuple[float, float]
    """Znormalizowana pozycja (x, y) środka dłoni."""
    fingers_up: List[bool]
    """Które palce są uniesione [kciuk, wsk, śr, serd, mały]."""
    finger_count: int
    """Liczba uniesionych palców (0–5)."""
    angles: HandAngles
    """Kąty kciuka."""


@dataclass
class FaceResult:
    """Wynik detekcji jednej twarzy."""
    landmarks: list


@dataclass
class PoseResult:
    """Wynik detekcji jednej pozy ciała."""
    landmarks: list


@dataclass
class DetectionResults:
    """Zbiorczy wynik detekcji dla jednej klatki."""
    hands: List[HandResult] = field(default_factory=list)
    faces: List[FaceResult] = field(default_factory=list)
    poses: List[PoseResult] = field(default_factory=list)
    fps: int = 0
    frame: Optional[np.ndarray] = None


# ── GestureTracker ────────────────────────────────────────


class GestureTracker:
    """
    Wysokopoziomowy tracker gestów.

    Przykłady użycia:

        # --- Tryb 1: pętla ręczna ---
        tracker = GestureTracker()
        tracker.open()
        while True:
            results = tracker.process_frame()
            if results is None:
                break
            for hand in results.hands:
                print(f"Pięść: {hand.is_fist}, palce: {hand.finger_count}")
            tracker.show(results.frame)
            if tracker.key_pressed("q"):
                break
        tracker.release()

        # --- Tryb 2: generator (najprostszy) ---
        with GestureTracker() as tracker:
            for frame, results in tracker.stream():
                for hand in results.hands:
                    print(hand.finger_count)

        # --- Tryb 3: tylko detekcja (bez kamery) ---
        tracker = GestureTracker(open_camera=False)
        frame = cv2.imread("foto.jpg")
        results = tracker.detect(frame, modes=["hands", "face"])
    """

    def __init__(
        self,
        camera_config: Optional[CameraConfig] = None,
        open_camera: bool = True,
        detect_modes: Optional[List[str]] = None,
    ):
        """
        Args:
            camera_config: konfiguracja kamery (domyślnie 1280×720)
            open_camera: czy od razu otwierać kamerę
            detect_modes: co wykrywać — lista z "hands", "face", "body"
                          (domyślnie: ["hands"])
        """
        self._camera = Camera(camera_config)
        self._detect_modes = detect_modes or ["hands"]
        self._analyzer = HandAnalyzer()
        self._prev_time = time.time()

        # Lazy-init detektorów (ładowane przy pierwszym użyciu)
        self._hand_det = None
        self._face_det = None
        self._pose_det = None

        if open_camera:
            self.open()

    # ── Lazy loading detektorów ───────────────────────────

    def _get_hand_detector(self):
        if self._hand_det is None:
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision

            self._hand_det = vision.HandLandmarker.create_from_options(
                vision.HandLandmarkerOptions(
                    base_options=python.BaseOptions(
                        model_asset_path=ensure_model("hand")
                    ),
                    num_hands=2,
                    min_hand_detection_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
            )
        return self._hand_det

    def _get_face_detector(self):
        if self._face_det is None:
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision

            self._face_det = vision.FaceLandmarker.create_from_options(
                vision.FaceLandmarkerOptions(
                    base_options=python.BaseOptions(
                        model_asset_path=ensure_model("face")
                    ),
                    num_faces=2,
                    min_face_detection_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
            )
        return self._face_det

    def _get_pose_detector(self):
        if self._pose_det is None:
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision

            self._pose_det = vision.PoseLandmarker.create_from_options(
                vision.PoseLandmarkerOptions(
                    base_options=python.BaseOptions(
                        model_asset_path=ensure_model("pose")
                    ),
                    num_poses=2,
                    min_pose_detection_confidence=0.5,
                    min_pose_presence_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
            )
        return self._pose_det

    # ── Kamera ────────────────────────────────────────────

    def open(self) -> "GestureTracker":
        """Otwiera kamerę."""
        self._camera.open()
        return self

    def release(self) -> None:
        """Zwalnia zasoby."""
        self._camera.release()

    @property
    def is_opened(self) -> bool:
        return self._camera.is_opened

    # ── Główna detekcja ───────────────────────────────────

    def detect(
        self,
        frame: np.ndarray,
        modes: Optional[List[str]] = None,
    ) -> DetectionResults:
        """
        Wykonuje detekcję na podanej klatce (bez kamery).

        Args:
            frame: klatka BGR (numpy array)
            modes: lista trybów ["hands", "face", "body"]
                   (domyślnie: self._detect_modes)

        Returns:
            DetectionResults z wykrytymi obiektami
        """
        modes = modes or self._detect_modes
        results = DetectionResults(frame=frame)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        if "hands" in modes:
            r = self._get_hand_detector().detect(mp_image)
            if r.hand_landmarks:
                for hand_lms in r.hand_landmarks:
                    results.hands.append(
                        HandResult(
                            landmarks=hand_lms,
                            is_fist=self._analyzer.is_fist(hand_lms),
                            palm_center=self._analyzer.palm_center(hand_lms),
                            fingers_up=self._analyzer.fingers_up(hand_lms),
                            finger_count=self._analyzer.count_fingers(hand_lms),
                            angles=self._analyzer.compute_angles(hand_lms),
                        )
                    )

        if "face" in modes:
            r = self._get_face_detector().detect(mp_image)
            if r.face_landmarks:
                for face_lms in r.face_landmarks:
                    results.faces.append(FaceResult(landmarks=face_lms))

        if "body" in modes:
            r = self._get_pose_detector().detect(mp_image)
            if r.pose_landmarks:
                for pose_lms in r.pose_landmarks:
                    results.poses.append(PoseResult(landmarks=pose_lms))

        # FPS
        now = time.time()
        dt = now - self._prev_time
        self._prev_time = now
        results.fps = int(1.0 / dt) if dt > 1e-6 else 0

        return results

    def read_frame(self) -> Optional[np.ndarray]:
        """Odczytuje klatkę z kamery (bez detekcji)."""
        return self._camera.read()

    def process_frame(
        self,
        modes: Optional[List[str]] = None,
        draw: bool = True,
    ) -> Optional[DetectionResults]:
        """
        Odczytuje klatkę z kamery, wykrywa i opcjonalnie rysuje.

        Args:
            modes: tryby detekcji
            draw: czy narysować landmarki na klatce

        Returns:
            DetectionResults lub None jeśli kamera nie działa
        """
        frame = self._camera.read()
        if frame is None:
            return None

        results = self.detect(frame, modes)

        if draw:
            self.draw_results(results)

        return results

    # ── Generator (stream) ────────────────────────────────

    def stream(
        self,
        modes: Optional[List[str]] = None,
        draw: bool = True,
        show: bool = True,
        quit_key: str = "q",
    ) -> Generator[Tuple[np.ndarray, DetectionResults], None, None]:
        """
        Generator — najwygodniejszy sposób użycia.

        Yields:
            (frame, DetectionResults) dla każdej klatki

        Przykład:
            with GestureTracker() as tracker:
                for frame, results in tracker.stream():
                    for hand in results.hands:
                        print(hand.finger_count)
        """
        while self.is_opened:
            results = self.process_frame(modes=modes, draw=draw)
            if results is None:
                continue

            if show:
                self.show(results.frame)

            yield results.frame, results

            if quit_key and self.key_pressed(quit_key):
                break

    # ── Rysowanie ─────────────────────────────────────────

    def draw_results(self, results: DetectionResults) -> None:
        """Rysuje wszystkie wyniki na klatce."""
        frame = results.frame
        if frame is None:
            return

        for hand in results.hands:
            drawing.draw_hand(frame, hand.landmarks)
            drawing.draw_hand_angles(frame, hand.landmarks, hand.angles)
            if hand.is_fist:
                drawing.draw_fist_badge(frame)
            drawing.draw_finger_count(frame, hand.finger_count)

        for face in results.faces:
            drawing.draw_face(frame, face.landmarks)

        for pose in results.poses:
            drawing.draw_pose(frame, pose.landmarks)

        mode_label = ", ".join(self._detect_modes)
        drawing.draw_hud(frame, mode_label, results.fps)

    # ── Okno / klawiatura ─────────────────────────────────

    @staticmethod
    def show(frame: np.ndarray, window_name: str = "GestureTracker") -> None:
        """Wyświetla klatkę."""
        Camera.show(frame, window_name)

    @staticmethod
    def key_pressed(key: str) -> bool:
        """Sprawdza czy naciśnięto dany klawisz."""
        return Camera.wait_key(1) == key

    # ── Context manager ───────────────────────────────────

    def __enter__(self) -> "GestureTracker":
        if not self.is_opened:
            self.open()
        return self

    def __exit__(self, *args) -> None:
        self.release()