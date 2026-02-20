"""Pobieranie i cache'owanie modeli MediaPipe."""

import os
import urllib.request

URLS = {
    "hand": (
        "https://storage.googleapis.com/mediapipe-models/"
        "hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
    ),
    "face": (
        "https://storage.googleapis.com/mediapipe-models/"
        "face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
    ),
    "pose": (
        "https://storage.googleapis.com/mediapipe-models/"
        "pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task"
    ),
}


def _cache_dir() -> str:
    """Zwraca ścieżkę do katalogu cache na modele."""
    base = os.getenv("LOCALAPPDATA") or os.path.join(
        os.path.expanduser("~"), ".cache"
    )
    path = os.path.join(base, "MediaPipeModels")
    os.makedirs(path, exist_ok=True)
    return path


def ensure_model(name: str) -> str:
    """
    Pobiera model jeśli nie istnieje w cache, zwraca ścieżkę do pliku.

    Args:
        name: "hand", "face" lub "pose"

    Returns:
        Ścieżka do pliku .task
    """
    if name not in URLS:
        raise ValueError(f"Nieznany model: {name!r}. Dostępne: {list(URLS)}")

    path = os.path.join(_cache_dir(), f"{name}.task")
    if not os.path.isfile(path):
        print(f"⬇️  Pobieram model: {name}")
        tmp = path + ".tmp"
        urllib.request.urlretrieve(URLS[name], tmp)
        os.replace(tmp, path)
        print(f"✅ Pobrano: {name}")
    return path