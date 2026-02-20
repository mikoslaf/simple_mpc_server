"""Analiza gestów – kąty, rozpoznawanie pięści, pozycja dłoni."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np


def _v3(lm) -> np.ndarray:
    """Konwertuje landmark MediaPipe na wektor 3D."""
    return np.array([lm.x, lm.y, lm.z], dtype=np.float32)


def _unit(v: np.ndarray) -> np.ndarray:
    """Zwraca wektor jednostkowy."""
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-6 else v


def angle_deg(v1: np.ndarray, v2: np.ndarray) -> float:
    """Kąt (w stopniach) między dwoma wektorami."""
    cos = float(np.clip(np.dot(_unit(v1), _unit(v2)), -1.0, 1.0))
    return float(np.degrees(np.arccos(cos)))


def is_right_angle(
    ang: float,
    min_deg: float = 75.0,
    max_deg: float = 105.0,
) -> bool:
    """Czy kąt jest bliski 90°."""
    return min_deg <= ang <= max_deg


# ── Analiza dłoni ──────────────────────────────────────────

@dataclass
class HandAngles:
    """Wynik analizy kątów dłoni."""
    thumb_palm: float
    thumb_index: float

    @property
    def thumb_palm_is_right(self) -> bool:
        return is_right_angle(self.thumb_palm)

    @property
    def thumb_index_is_right(self) -> bool:
        return is_right_angle(self.thumb_index)


class HandAnalyzer:
    """Metody analizy gestów dłoni."""

    @staticmethod
    def compute_angles(landmarks) -> HandAngles:
        """
        Oblicza kąty kciuka względem dłoni i palca wskazującego.

        Args:
            landmarks: lista 21 landmarków dłoni z MediaPipe

        Returns:
            HandAngles z kątami w stopniach
        """
        p9 = _v3(landmarks[9])
        p12 = _v3(landmarks[12])
        p5 = _v3(landmarks[5])
        p8 = _v3(landmarks[8])
        p2 = _v3(landmarks[2])
        p4 = _v3(landmarks[4])

        palm_axis = p9 - p12
        index_axis = p5 - p8
        thumb_dir = p4 - p2

        return HandAngles(
            thumb_palm=angle_deg(thumb_dir, palm_axis),
            thumb_index=angle_deg(palm_axis, index_axis),
        )

    @staticmethod
    def is_fist(landmarks) -> bool:
        """
        Sprawdza czy dłoń jest zaciśnięta w pięść.

        Args:
            landmarks: lista 21 landmarków dłoni

        Returns:
            True jeśli gest to pięść
        """
        # Środek dłoni
        palm_idxs = [0, 5, 9, 13, 17]
        palm_pts = [_v3(landmarks[i]) for i in palm_idxs]
        palm = sum(palm_pts) / len(palm_pts)

        # Skala dłoni
        wrist = _v3(landmarks[0])
        mid_mcp = _v3(landmarks[9])
        span = float(np.linalg.norm(wrist - mid_mcp))
        if span < 1e-6:
            return False

        # Sprawdź palce (bez kciuka) – czy końcówki są blisko dłoni
        tips = [8, 12, 16, 20]
        dists = [float(np.linalg.norm(_v3(landmarks[t]) - palm)) for t in tips]
        thresh = 0.4 * span
        fingers_folded = all(d < thresh for d in dists)

        # Sprawdź kciuk
        thumb_tip = _v3(landmarks[4])
        thumb_mcp = _v3(landmarks[2])
        thumb_dir = thumb_tip - thumb_mcp
        index_mcp = _v3(landmarks[5])
        palm_axis = mid_mcp - wrist

        dist_thumb_palm = float(np.linalg.norm(thumb_tip - palm))
        dist_thumb_index = float(np.linalg.norm(thumb_tip - index_mcp))
        ang_thumb_palm = angle_deg(thumb_dir, palm_axis)

        thumb_close = dist_thumb_palm < (0.35 * span)
        thumb_tucked = dist_thumb_index < (0.28 * span)
        thumb_across = ang_thumb_palm > 100.0
        thumb_folded = thumb_close or thumb_tucked or thumb_across

        return fingers_folded and thumb_folded

    @staticmethod
    def palm_center(landmarks) -> Tuple[float, float]:
        """
        Zwraca znormalizowaną pozycję (x, y) środka dłoni.

        Wartości 0.0–1.0, gdzie (0,0) = lewy-górny róg.
        """
        idxs = [0, 5, 9, 13, 17]
        pts = [_v3(landmarks[i]) for i in idxs]
        center = sum(pts) / len(pts)
        return float(center[0]), float(center[1])

    @staticmethod
    def fingertips(landmarks) -> List[Tuple[float, float]]:
        """
        Zwraca pozycje (x,y) końcówek 5 palców.

        Kolejność: kciuk, wskazujący, środkowy, serdeczny, mały.
        """
        tip_idxs = [4, 8, 12, 16, 20]
        return [(float(landmarks[i].x), float(landmarks[i].y)) for i in tip_idxs]

    @staticmethod
    def fingers_up(landmarks) -> List[bool]:
        """
        Sprawdza które palce są wyprostowane (uniesione).

        Returns:
            Lista 5 bool: [kciuk, wskazujący, środkowy, serdeczny, mały]
        """
        # Porównanie: tip wyżej niż PIP (mniejszy y = wyżej)
        tip_pip_pairs = [
            (4, 3),   # kciuk: tip vs IP
            (8, 6),   # wskazujący: tip vs PIP
            (12, 10), # środkowy
            (16, 14), # serdeczny
            (20, 18), # mały
        ]
        result = []
        for tip_idx, pip_idx in tip_pip_pairs:
            tip_y = landmarks[tip_idx].y
            pip_y = landmarks[pip_idx].y
            result.append(tip_y < pip_y)
        return result

    @staticmethod
    def count_fingers(landmarks) -> int:
        """Liczy ile palców jest uniesionych (0–5)."""
        return sum(HandAnalyzer.fingers_up(landmarks))