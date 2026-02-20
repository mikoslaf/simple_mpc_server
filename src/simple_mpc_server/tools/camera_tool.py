from pathlib import Path
from loguru import logger
from mcp.server.fastmcp import FastMCP
from simple_mpc_server.core.tool_response import ToolResponse
from simple_mpc_server.core.Atool import ATool
import cv2
import tempfile
import json
import time
from collections import deque
from statistics import mode, multimode

# Zakładamy, że GestureTracker jest dostępny w Twoim środowisku
from simple_mpc_server.gesture_tracker.detector import GestureTracker

class CameraTool(ATool):
    """Narzędzie do detekcji gestów z zaawansowaną stabilizacją wyników."""

    def __init__(self):
        super().__init__()
        self._output_dir = Path(tempfile.gettempdir()) / "camera_tool"
        self._output_dir.mkdir(parents=True, exist_ok=True)
        
        # Konfiguracja stabilizacji
        self.stability_window_seconds = 0.8  # Czas obserwacji dla potwierdzenia gestu
        self.min_confidence_ratio = 0.7      # Minimalny % klatek, które muszą się zgadzać

    def _save_frame(self, frame) -> str:
        path = self._output_dir / f"capture_{int(time.time())}.jpg"
        cv2.imwrite(str(path), frame)
        return str(path)

    def _analyze_gesture_stability(self, readings: list[dict]) -> dict:
        """
        Analizuje listę surowych odczytów i zwraca najbardziej prawdopodobny, stabilny gest.
        Eliminuje szum i migotanie detekcji.
        """
        if not readings:
            return {"gesture": "none", "confidence": 0.0, "details": {}}

        # 1. Ekstrakcja kluczowych metryk z każdej klatki
        finger_counts = [r['count'] for r in readings]
        is_fists = [r['is_fist'] for r in readings]
        
        # 2. Wyznaczanie dominującego stanu (Majority Voting)
        # Używamy multimode, aby obsłużyć remisy, ale bierzemy pierwszy wynik jako dominantę
        try:
            dominant_count = mode(finger_counts)
            dominant_fist = mode(is_fists)
        except Exception:
            # Fallback jeśli brak danych lub błąd statystyki
            dominant_count = finger_counts[-1] if finger_counts else 0
            dominant_fist = is_fists[-1] if is_fists else False

        # 3. Obliczanie wskaźnika pewności (jak często wystąpił dominujący wynik)
        count_confidence = finger_counts.count(dominant_count) / len(finger_counts)
        fist_confidence = is_fists.count(dominant_fist) / len(is_fists)
        
        overall_confidence = (count_confidence + fist_confidence) / 2

        # 4. Logika biznesowa gestów (wykraczająca poza prosty licznik)
        detected_gesture = "unknown"
        details = {
            "dominant_finger_count": dominant_count,
            "is_dominant_fist": dominant_fist,
            "raw_readings_count": len(readings),
            "stability_score": round(overall_confidence, 2)
        }

        if overall_confidence < self.min_confidence_ratio:
            detected_gesture = "unstable"
            details["reason"] = "Zbyt duża zmienność wykrycia"
        elif dominant_fist and fist_confidence > 0.8:
            detected_gesture = "fist"
        elif dominant_count == 0:
            detected_gesture = "open_palm_or_no_hand" # Trudne do rozróżnienia bez bounding boxa
        elif dominant_count == 1:
            # Sprawdzenie czy to kciuk czy wskazujący (prosta heurystyka)
            # W pełnej wersji warto sprawdzić which_finger_up z readings
            detected_gesture = "one_finger"
        elif dominant_count == 2:
            detected_gesture = "two_fingers" # Może być "V" lub "OK" - wymaga dalszej analizy pozycji
        elif dominant_count == 5:
            detected_gesture = "open_hand"
        else:
            detected_gesture = f"{dominant_count}_fingers"

        # Agregacja uniesionych palców (najczęstszy wzorzec)
        # Grupujemy tuple palców i szukamy najczęstszej kombinacji
        finger_patterns = [tuple(r.get('up', [])) for r in readings if 'up' in r]
        if finger_patterns:
            try:
                most_common_fingers = mode(finger_patterns)
                details["active_fingers"] = list(most_common_fingers)
            except Exception:
                details["active_fingers"] = []

        return {
            "gesture": detected_gesture,
            "confidence": overall_confidence,
            "details": details
        }

    def register(self, mcp: FastMCP) -> None:
        
        @mcp.tool(name="camera_detect_gesture_stable")
        def camera_detect_gesture_stable(duration: float = 2.0) -> str:
            """
            Zaawansowana detekcja gestów z filtrowaniem szumu.
            Obserwuje ruch przez podany czas i zwraca najbardziej stabilny gest.
            
            Args:
                duration: Czas obserwacji w sekundach (zalecane min. 1.5s dla stabilności)
            """
            logger.info(f"Rozpoczynanie stabilnej detekcji gestów na {duration}s")
            
            finger_names = ["Kciuk", "Wskazujący", "Środkowy", "Serdeczny", "Mały"]
            raw_readings = []
            
            try:
                start_time = time.time()
                
                with GestureTracker(detect_modes=["hands"]) as tracker:
                    for frame, results in tracker.stream():
                        current_time = time.time()
                        if current_time - start_time > duration:
                            break
                        
                        for hand in results.hands:
                            # Pobieranie danych z klatki
                            fingers_up = []
                            if hasattr(hand, 'fingers_up') and hand.fingers_up:
                                fingers_up = [n for n, f in zip(finger_names, hand.fingers_up) if f]
                            
                            reading = {
                                "timestamp": current_time,
                                "count": hand.finger_count if hasattr(hand, 'finger_count') else 0,
                                "is_fist": hand.is_fist if hasattr(hand, 'is_fist') else False,
                                "up": fingers_up,
                                # Jeśli tracker ma confidence score dla landmarków, warto to dodać
                                # "landmark_confidence": hand.confidence 
                            }
                            raw_readings.append(reading)
                            
                            # Opcjonalny debug w logach (można wyłączyć w produkcji)
                            # logger.debug(f"Klatka: {reading['count']} palców, pięść: {reading['is_fist']}")

                if not raw_readings:
                    return json.dumps({
                        "success": True,
                        "data": {"gesture": "no_hand_detected", "confidence": 0},
                        "description": "Nie wykryto żadnej dłoni w podanym czasie."
                    }, ensure_ascii=False)

                # ANALIZA STABILNOŚCI
                analysis_result = self._analyze_gesture_stability(raw_readings)
                
                response_msg = f"Wykryto gest: {analysis_result['gesture']} (Pewność: {analysis_result['confidence']:.0%})"
                if analysis_result['details'].get('active_fingers'):
                    response_msg += f" - Aktywne: {', '.join(analysis_result['details']['active_fingers'])}"

                return json.dumps({
                    "success": True,
                    "data": {
                        "gesture": analysis_result['gesture'],
                        "confidence": analysis_result['confidence'],
                        "details": analysis_result['details'],
                        "samples_analyzed": len(raw_readings)
                    },
                    "description": response_msg
                }, ensure_ascii=False)

            except Exception as e:
                logger.error(f"Błąd podczas detekcji gestu: {e}", exc_info=True)
                return json.dumps({
                    "success": False, 
                    "data": None, 
                    "description": f"Krytyczny błąd: {str(e)}"
                }, ensure_ascii=False)

        # Pozostałe metody (camera_stream_hands, etc.) mogą pozostać bez zmian 
        # lub również wykorzystać _analyze_gesture_stability jeśli potrzebują większej precyzji.
        # Dla brevity pomijam ich ponowne przepisywanie, ale zasada jest ta sama.