"""Obsługa kamery (OpenCV)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np


@dataclass
class CameraConfig:
    """Konfiguracja kamery."""
    device_id: int = 0
    width: int = 1280
    height: int = 720
    flip_horizontal: bool = True


class Camera:
    """
    Wrapper na cv2.VideoCapture z wygodnymi metodami.

    Przykład:
        cam = Camera()
        cam.open()
        frame = cam.read()
        cam.release()

    Lub jako context manager:
        with Camera() as cam:
            frame = cam.read()
    """

    def __init__(self, config: Optional[CameraConfig] = None):
        self.config = config or CameraConfig()
        self._cap: Optional[cv2.VideoCapture] = None
        self._prev_time: float = 0.0

    # ── Otwieranie / zamykanie ─────────────────────────────

    def open(self) -> "Camera":
        """Otwiera kamerę. Zwraca self dla łańcuchowania."""
        if self._cap is not None:
            self.release()

        self._cap = cv2.VideoCapture(self.config.device_id)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
        self._prev_time = time.time()

        if not self._cap.isOpened():
            raise RuntimeError(
                f"Nie udało się otworzyć kamery (device_id={self.config.device_id})"
            )
        return self

    def release(self) -> None:
        """Zwalnia kamerę i zamyka okna OpenCV."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        cv2.destroyAllWindows()

    @property
    def is_opened(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    # ── Odczyt klatek ──────────────────────────────────────

    def read(self) -> Optional[np.ndarray]:
        """
        Odczytuje jedną klatkę z kamery.

        Returns:
            Klatka BGR jako numpy array, lub None jeśli odczyt się nie udał.
        """
        if not self.is_opened:
            return None

        ok, frame = self._cap.read()
        if not ok:
            return None

        if self.config.flip_horizontal:
            frame = cv2.flip(frame, 1)

        return frame

    def fps(self) -> int:
        """Zwraca aktualny FPS (na podstawie czasu między klatkami)."""
        now = time.time()
        dt = now - self._prev_time
        self._prev_time = now
        return int(1.0 / dt) if dt > 1e-6 else 0

    # ── Wyświetlanie ───────────────────────────────────────

    @staticmethod
    def show(frame: np.ndarray, window_name: str = "GestureTracker") -> None:
        """Wyświetla klatkę w oknie OpenCV."""
        cv2.imshow(window_name, frame)

    @staticmethod
    def wait_key(delay_ms: int = 1) -> str:
        """
        Czeka na klawisz. Zwraca znak lub "" jeśli nic nie naciśnięto.
        """
        k = cv2.waitKey(delay_ms) & 0xFF
        return chr(k) if 0 < k < 128 else ""

    # ── Context manager ────────────────────────────────────

    def __enter__(self) -> "Camera":
        return self.open()

    def __exit__(self, *args) -> None:
        self.release()