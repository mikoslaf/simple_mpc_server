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

    # Indeksy kluczowych punktów dla czytelności
    WRIST = 0
    THUMB_TIP = 4
    THUMB_IP = 3
    THUMB_MCP = 2
    INDEX_PIP = 6
    INDEX_TIP = 8
    MIDDLE_PIP = 10
    MIDDLE_TIP = 12
    RING_PIP = 14
    RING_TIP = 16
    PINKY_PIP = 18
    PINKY_TIP = 20
    
    # Palce (bez kciuka) - ich końcówki i PIP'y
    FINGERS = [
        (INDEX_TIP, INDEX_PIP),
        (MIDDLE_TIP, MIDDLE_PIP),
        (RING_TIP, RING_PIP),
        (PINKY_TIP, PINKY_PIP)
    ]

    @staticmethod
    def compute_angles(landmarks) -> HandAngles:
        """
        Oblicza kąty kciuka względem dłoni i palca wskazującego.
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
        Poprawiona logika oparta na kątach i odległościach w przestrzeni 3D.
        """
        wrist = _v3(landmarks[HandAnalyzer.WRIST])
        mid_mcp = _v3(landmarks[9])
        
        # Skala dłoni jako odległość od nadgarstka do środka dłoni
        hand_scale = float(np.linalg.norm(wrist - mid_mcp))
        if hand_scale < 1e-6:
            return False

        # Sprawdzenie palców (bez kciuka): czy są "zagięte"
        # Palec jest zgięty, jeśli jego końcówka jest bliżej nadgarstka niż jego własny PIP.
        fingers_folded_count = 0
        for tip_idx, pip_idx in HandAnalyzer.FINGERS:
            tip_to_wrist = np.linalg.norm(_v3(landmarks[tip_idx]) - wrist)
            pip_to_wrist = np.linalg.norm(_v3(landmarks[pip_idx]) - wrist)
            if tip_to_wrist < pip_to_wrist:
                fingers_folded_count += 1

        # Jeśli większość palców (3 z 4) jest zgiętych, to prawdopodobnie pięść
        fingers_condition = fingers_folded_count >= 3

        # Sprawdzenie kciuka: czy jest "schowany" pod palcem wskazującym lub blisko dłoni
        thumb_tip = _v3(landmarks[HandAnalyzer.THUMB_TIP])
        thumb_ip = _v3(landmarks[HandAnalyzer.THUMB_IP])
        index_mcp = _v3(landmarks[5])
        
        # Odległość między kciukiem a palcem wskazującym
        thumb_index_dist = np.linalg.norm(thumb_tip - index_mcp)
        # Odległość kciuka od "centrum" dłoni (nadgarstek)
        thumb_palm_dist = np.linalg.norm(thumb_tip - wrist)

        # Kciuk jest zgięty/ukryty, jeśli jest blisko innych palców lub dłoni
        thumb_condition = thumb_index_dist < (0.3 * hand_scale) or thumb_palm_dist < (0.4 * hand_scale)

        return fingers_condition and thumb_condition

    @staticmethod
    def palm_center(landmarks) -> Tuple[float, float]:
        """
        Zwraca znormalizowaną pozycję (x, y) środka dłoni.
        """
        idxs = [0, 5, 9, 13, 17]
        pts = [_v3(landmarks[i]) for i in idxs]
        center = sum(pts) / len(pts)
        return float(center[0]), float(center[1])

    @staticmethod
    def fingertips(landmarks) -> List[Tuple[float, float]]:
        """
        Zwraca pozycje (x,y) końcówek 5 palców.
        """
        tip_idxs = [4, 8, 12, 16, 20]
        return [(float(landmarks[i].x), float(landmarks[i].y)) for i in tip_idxs]

    @staticmethod
    def fingers_up(landmarks) -> List[bool]:
        """
        Sprawdza które palce są wyprostowane (uniesione).
        Poprawiona logika oparta na kątach stawów PIP i DIP.

        Returns:
            Lista 5 bool: [kciuk, wskazujący, środkowy, serdeczny, mały]
        """
        result = [False] * 5

        # Kciuk: porównujemy IP (interphalangeal joint) z MCP (metacarpophalangeal)
        # Jeśli IP jest wyżej niż MCP, to kciuk jest uniesiony.
        thumb_ip_y = landmarks[HandAnalyzer.THUMB_IP].y
        thumb_mcp_y = landmarks[HandAnalyzer.THUMB_MCP].y
        result[0] = thumb_ip_y < thumb_mcp_y

        # Pozostałe palce: porównujemy TIP z PIP
        # Jeśli TIP jest wyżej (mniejszy Y) niż PIP, to palec jest uniesiony.
        for i, (tip_idx, pip_idx) in enumerate(HandAnalyzer.FINGERS):
            tip_y = landmarks[tip_idx].y
            pip_y = landmarks[pip_idx].y
            result[i + 1] = tip_y < pip_y

        return result

    @staticmethod
    def count_fingers(landmarks) -> int:
        """Liczy ile palców jest uniesionych (0–5)."""
        return sum(HandAnalyzer.fingers_up(landmarks))