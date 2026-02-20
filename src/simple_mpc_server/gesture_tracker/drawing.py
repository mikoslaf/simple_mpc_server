"""Rysowanie landmarków i UI na klatkach wideo."""

from __future__ import annotations

from typing import List, Tuple, Optional

import cv2
import numpy as np

from .analysis import HandAnalyzer, HandAngles


# ── Definicje połączeń ────────────────────────────────────

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (0, 9), (9, 10), (10, 11), (11, 12),
    (0, 13), (13, 14), (14, 15), (15, 16),
    (0, 17), (17, 18), (18, 19), (19, 20),
    (5, 9), (9, 13), (13, 17),
]

POSE_CONNECTIONS = [
    (11, 12),
    (11, 13), (13, 15),
    (12, 14), (14, 16),
    (11, 23), (12, 24),
    (23, 24),
    (23, 25), (25, 27),
    (24, 26), (26, 28),
    (27, 31), (28, 32),
]


# ── Rysowanie szkieletu ──────────────────────────────────

def draw_landmarks(
    frame: np.ndarray,
    landmarks,
    connections: List[Tuple[int, int]],
    line_color: Tuple[int, int, int] = (0, 255, 0),
    point_color: Tuple[int, int, int] = (0, 0, 255),
    line_width: int = 2,
    point_radius: int = 3,
) -> None:
    """Rysuje landmarki i połączenia na klatce."""
    h, w = frame.shape[:2]
    # Linie
    for a, b in connections:
        pt1 = (int(landmarks[a].x * w), int(landmarks[a].y * h))
        pt2 = (int(landmarks[b].x * w), int(landmarks[b].y * h))
        cv2.line(frame, pt1, pt2, line_color, line_width)
    # Punkty
    for lm in landmarks:
        cv2.circle(frame, (int(lm.x * w), int(lm.y * h)), point_radius, point_color, -1)


def draw_hand(frame: np.ndarray, landmarks, **kwargs) -> None:
    """Rysuje szkielet dłoni."""
    draw_landmarks(frame, landmarks, HAND_CONNECTIONS, point_radius=5, **kwargs)


def draw_face(
    frame: np.ndarray,
    landmarks,
    color: Tuple[int, int, int] = (0, 255, 0),
    radius: int = 1,
) -> None:
    """Rysuje punkty twarzy."""
    h, w = frame.shape[:2]
    for lm in landmarks:
        cv2.circle(frame, (int(lm.x * w), int(lm.y * h)), radius, color, -1)


def draw_pose(frame: np.ndarray, landmarks, **kwargs) -> None:
    """Rysuje szkielet pozy ciała."""
    draw_landmarks(frame, landmarks, POSE_CONNECTIONS, **kwargs)


# ── Rysowanie informacji tekstowych ──────────────────────

def draw_hand_angles(
    frame: np.ndarray,
    landmarks,
    angles: HandAngles,
) -> None:
    """Rysuje kąty dłoni obok nadgarstka."""
    h, w = frame.shape[:2]
    wx = int(landmarks[0].x * w)
    wy = int(landmarks[0].y * h)

    r90_1 = " (≈90°)" if angles.thumb_palm_is_right else ""
    r90_2 = " (≈90°)" if angles.thumb_index_is_right else ""
    t1 = f"kciuk-dlon: {angles.thumb_palm:.1f}{r90_1}"
    t2 = f"kciuk-wsk:  {angles.thumb_index:.1f}{r90_2}"

    y0 = max(25, wy - 30)
    cv2.putText(frame, t1, (wx + 10, y0), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
    cv2.putText(frame, t2, (wx + 10, y0 + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)


def draw_fist_badge(frame: np.ndarray) -> None:
    """Rysuje napis PIĘŚĆ w prawym-górnym rogu."""
    text = "PIESC"
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale, thickness = 0.9, 2
    (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
    x = frame.shape[1] - tw - 16
    y = 30
    cv2.rectangle(frame, (x - 6, y - th - 6), (x + tw + 6, y + 6), (0, 0, 0), -1)
    cv2.putText(frame, text, (x, y), font, scale, (0, 255, 0), thickness)


def draw_finger_count(frame: np.ndarray, count: int) -> None:
    """Rysuje liczbę uniesionych palców."""
    text = f"Palce: {count}"
    cv2.putText(frame, text, (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)


def draw_hud(
    frame: np.ndarray,
    mode: str,
    fps: int,
    extra: str = "",
) -> None:
    """Rysuje pasek informacyjny (HUD)."""
    labels = {"hands": "RĘCE", "face": "TWARZ", "body": "CIAŁO"}
    label = labels.get(mode, mode.upper())
    cv2.putText(
        frame, f"{label} | FPS: {fps} {extra}",
        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2,
    )