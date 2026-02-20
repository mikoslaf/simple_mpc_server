"""
Przykłady użycia modułu gesture_tracker.
Uruchom: python -m gesture_tracker.demo
"""

from simple_mpc_server.gesture_tracker.detector import GestureTracker

def example_simple():
    """Najprostszy przykład — stream z generatorem."""
    print("=== Przykład 1: prosty stream ===")
    print("Pokaż dłoń do kamery. q = wyjście")

    with GestureTracker(detect_modes=["hands"]) as tracker:
        for frame, results in tracker.stream():
            for hand in results.hands:
                status = "PIĘŚĆ" if hand.is_fist else f"Palce: {hand.finger_count}"
                print(f"  {status} | pozycja: ({hand.palm_center[0]:.2f}, {hand.palm_center[1]:.2f})")


def example_multi_mode():
    """Detekcja dłoni + twarzy jednocześnie."""
    print("=== Przykład 2: dłonie + twarz ===")

    with GestureTracker(detect_modes=["hands", "face"]) as tracker:
        for frame, results in tracker.stream():
            if results.hands:
                print(f"  Dłonie: {len(results.hands)}")
            if results.faces:
                print(f"  Twarze: {len(results.faces)}")


def example_manual_loop():
    """Pętla ręczna — pełna kontrola."""
    print("=== Przykład 3: pętla ręczna ===")

    tracker = GestureTracker(detect_modes=["hands"])
    tracker.open()

    try:
        while tracker.is_opened:
            results = tracker.process_frame(draw=True)
            if results is None:
                continue

            # Własna logika
            for hand in results.hands:
                if hand.is_fist:
                    print("PIĘŚĆ!")
                elif hand.finger_count == 2:
                    print("✌️ Peace!")
                elif hand.finger_count == 5:
                    print("🖐️ Piątka!")

            tracker.show(results.frame)
            if tracker.key_pressed("q"):
                break
    finally:
        tracker.release()


def example_no_camera():
    """Detekcja na pojedynczym obrazie (bez kamery)."""
    import cv2

    print("=== Przykład 4: detekcja na zdjęciu ===")

    tracker = GestureTracker(open_camera=False)

    frame = cv2.imread("test_photo.jpg")
    if frame is None:
        print("Brak pliku test_photo.jpg, pomijam.")
        return

    results = tracker.detect(frame, modes=["hands", "face", "body"])
    print(f"  Dłonie: {len(results.hands)}")
    print(f"  Twarze: {len(results.faces)}")
    print(f"  Pozy:   {len(results.poses)}")

    for i, hand in enumerate(results.hands):
        print(f"  Dłoń {i}: pięść={hand.is_fist}, palce={hand.finger_count}")

    tracker.draw_results(results)
    cv2.imshow("Wynik", results.frame)
    cv2.waitKey(0)


def example_finger_counter():
    """Licznik palców na żywo."""
    print("=== Przykład 5: licznik palców ===")
    print("Pokaż palce do kamery!")

    with GestureTracker() as tracker:
        for frame, results in tracker.stream():
            for hand in results.hands:
                fingers = hand.fingers_up
                names = ["Kciuk", "Wskazujący", "Środkowy", "Serdeczny", "Mały"]
                up = [n for n, f in zip(names, fingers) if f]
                print(f"  Uniesione ({hand.finger_count}): {', '.join(up) or 'żaden'}")


# ── Main ──────────────────────────────────────────────────

if __name__ == "__main__":
    print("Wybierz przykład:")
    print("  1 — prosty stream")
    print("  2 — dłonie + twarz")
    print("  3 — pętla ręczna")
    print("  4 — detekcja na zdjęciu")
    print("  5 — licznik palców")

    choice = input("Numer: ").strip()
    examples = {
        "1": example_simple,
        "2": example_multi_mode,
        "3": example_manual_loop,
        "4": example_no_camera,
        "5": example_finger_counter,
    }

    fn = examples.get(choice)
    if fn:
        fn()
    else:
        print("Nieznany wybór, uruchamiam przykład 1")
        example_simple()