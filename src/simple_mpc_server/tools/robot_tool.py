import time

from loguru import logger
from mcp.server.fastmcp import FastMCP

from simple_mpc_server.core.Atool import ATool
from simple_mpc_server.core.arduino_board import ArduinoBoard
from simple_mpc_server.core.tool_response import ToolResponse


class RobotTool(ATool):
    """Narzędzie MCP do sterowania robotem na dwóch serwach.

    Robot rozumie tekstowe komendy (po stronie szkicu Arduino):

    - "servo1 stop" / "servo2 stop"
    - "servo1 rotate <deg>" / "servo2 rotate <deg>"
    - "servo1 spin <ms>" / "servo2 spin <ms>"
    - "rotateBoth <deg1> <deg2>" (alias: rotateBothBlocking) - obraca oba serwa jednocześnie

    To narzędzie udostępnia wygodne komendy wysokiego poziomu
    (jazda prosto, cofanie, obrót w miejscu) oraz komendę ogólną
    do wysyłania pojedynczej instrukcji tekstowej.
    """

    def __init__(self, port: str | None = None, baudrate: int = 115200) -> None:
        self._port: str | None = port
        self._baudrate: int = baudrate
        self._board: ArduinoBoard | None = None

    def _ensure_connected(self) -> tuple[bool, str]:
        """Upewnia się, że istnieje aktywne połączenie z Arduino."""

        if self._board and self._board.is_connected():
            return True, ""

        if not self._port:
            return False, "Port nie został ustawiony. Wywołaj najpierw narzędzie 'robot_connect'."

        logger.debug(f"Próba połączenia z Arduino (robot) na porcie {self._port} ({self._baudrate} bps)")
        board = ArduinoBoard(self._port, self._baudrate)
        if not board.connect():
            return False, f"Nie udało się połączyć z Arduino na porcie {self._port}."

        self._board = board
        return True, ""

    def register(self, mcp: FastMCP) -> None:
        """Rejestruje narzędzia do sterowania robotem na serwach."""

        @mcp.tool(name="robot_connect")
        def robot_connect(port: str = "COM4", baudrate: int = 115200) -> ToolResponse[str]:
            """Nawiązuje połączenie z płytką Arduino sterującą robotem.

            Parametry:
            - port: np. "COM4" na Windows
            - baudrate: domyślnie 115200
            """

            self._port = port
            self._baudrate = baudrate

            logger.debug(f"Łączenie z Arduino (robot) na porcie {port} ({baudrate} bps)")
            board = ArduinoBoard(port, baudrate)
            if not board.connect():
                logger.error(f"Nie udało się połączyć z Arduino na porcie {port}")
                self._board = None
                return ToolResponse.fail(f"Nie udało się połączyć z Arduino na porcie {port}.")

            self._board = board
            return ToolResponse.ok(
                f"Połączono z Arduino (robot) na porcie {port}.",
                f"Połączono z robotem (Arduino, {port}, {baudrate} bps).",
            )

        @mcp.tool(name="robot_disconnect")
        def robot_disconnect() -> ToolResponse[str]:
            """Rozłącza aktualne połączenie z Arduino (robotem)."""

            if not self._board or not self._board.is_connected():
                return ToolResponse.fail("Brak aktywnego połączenia z robotem.")

            try:
                self._board.disconnect()
                self._board = None
                return ToolResponse.ok("Rozłączono z robotem.", "Połączenie UART z robotem zostało zamknięte.")
            except Exception as exc:  # pragma: no cover - zabezpieczenie na niespodziewany błąd
                logger.error(f"Błąd podczas rozłączania z robotem: {exc}")
                return ToolResponse.fail("Wystąpił błąd podczas rozłączania z robotem.")

        def _send_robot_command(command: str) -> tuple[bool, str]:
            """Wysyła pojedynczą komendę tekstową do robota i zwraca (ok, opis)."""

            ok, msg = self._ensure_connected()
            if not ok:
                logger.error(msg)
                return False, msg

            assert self._board is not None

            logger.debug(f"Wysyłanie komendy do robota: {command}")
            if not self._board.send_command(command):
                return False, f"Nie udało się wysłać komendy '{command}' do robota."

            time.sleep(0.05)
            response = self._board.read_response()
            if response:
                return True, f"Odpowiedź z robota: {response}"
            return True, "Komenda wysłana, brak odpowiedzi z robota."

        @mcp.tool(name="robot_send_command")
        def robot_send_command(command: str) -> ToolResponse[str]:
            """Wysyła surową komendę tekstową do robota.

            Przykłady:
            - "servo1 stop"
            - "servo2 rotate 90"
            - "servo1 spin 1500"
            """

            ok, desc = _send_robot_command(command)
            if not ok:
                return ToolResponse.fail(desc)
            return ToolResponse.ok("OK", desc)

        @mcp.tool(name="robot_forward")
        def robot_forward(rotations: int = 1) -> ToolResponse[str]:
            """Jazda prosto: obracanie obu serw o 360° * rotations jednocześnie (rotateBoth)."""

            total_deg = 360 * rotations
            ok, desc = _send_robot_command(f"rotateBoth {total_deg} {total_deg}")
            if not ok:
                return ToolResponse.fail(desc)

            return ToolResponse.ok(
                "OK",
                f"Robot jedzie prosto ({rotations} obrót/obroty, {total_deg}° na każde servo). {desc}",
            )

        @mcp.tool(name="robot_backward")
        def robot_backward(rotations: int = 1) -> ToolResponse[str]:
            """Cofanie: obracanie obu serw w przeciwną stronę o 360° * rotations jednocześnie (rotateBoth)."""

            total_deg = -360 * rotations
            ok, desc = _send_robot_command(f"rotateBoth {total_deg} {total_deg}")
            if not ok:
                return ToolResponse.fail(desc)

            return ToolResponse.ok(
                "OK",
                f"Robot cofa ({rotations} obrót/obroty, {total_deg}° na każde servo). {desc}",
            )

        @mcp.tool(name="robot_turn_left")
        def robot_turn_left(rotations: int = 1) -> ToolResponse[str]:
            """Obrót w lewo: oba serwa obracają się w przeciwnych kierunkach (rotateBoth).
            
            Servo1 do przodu, servo2 do tyłu - robot obraca się w miejscu w lewo.
            """

            total_deg = 360 * rotations
            ok, desc = _send_robot_command(f"rotateBoth {total_deg} {-total_deg}")
            if not ok:
                return ToolResponse.fail(desc)

            return ToolResponse.ok(
                "OK",
                f"Robot obraca się w lewo ({rotations} obrót/obroty, servo1={total_deg}°, servo2={-total_deg}°). {desc}",
            )

        @mcp.tool(name="robot_turn_right")
        def robot_turn_right(rotations: int = 1) -> ToolResponse[str]:
            """Obrót w prawo: oba serwa obracają się w przeciwnych kierunkach (rotateBoth).
            
            Servo1 do tyłu, servo2 do przodu - robot obraca się w miejscu w prawo.
            """

            total_deg = 360 * rotations
            ok, desc = _send_robot_command(f"rotateBoth {-total_deg} {total_deg}")
            if not ok:
                return ToolResponse.fail(desc)

            return ToolResponse.ok(
                "OK",
                f"Robot obraca się w prawo ({rotations} obrót/obroty, servo1={-total_deg}°, servo2={total_deg}°). {desc}",
            )

        @mcp.tool(name="robot_rotate_servo1")
        def robot_rotate_servo1(degrees: int) -> ToolResponse[str]:
            """Obracanie tylko serwa 1 o podaną liczbę stopni.
            
            Parametry:
            - degrees: kąt obrotu w stopniach (dodatni lub ujemny)
            """

            ok, desc = _send_robot_command(f"servo1 rotate {degrees}")
            if not ok:
                return ToolResponse.fail(desc)

            return ToolResponse.ok(
                "OK",
                f"Servo1 obrócone o {degrees}°. {desc}",
            )

        @mcp.tool(name="robot_rotate_servo2")
        def robot_rotate_servo2(degrees: int) -> ToolResponse[str]:
            """Obracanie tylko serwa 2 o podaną liczbę stopni.
            
            Parametry:
            - degrees: kąt obrotu w stopniach (dodatni lub ujemny)
            """

            ok, desc = _send_robot_command(f"servo2 rotate {degrees}")
            if not ok:
                return ToolResponse.fail(desc)

            return ToolResponse.ok(
                "OK",
                f"Servo2 obrócone o {degrees}°. {desc}",
            )

        @mcp.tool(name="robot_stop")
        def robot_stop() -> ToolResponse[str]:
            """Zatrzymuje robota: wysyła "servo1 stop" i "servo2 stop"."""

            commands = ["servo1 stop", "servo2 stop"]
            descriptions: list[str] = []

            for cmd in commands:
                ok, desc = _send_robot_command(cmd)
                if not ok:
                    return ToolResponse.fail(desc)
                descriptions.append(desc)

            return ToolResponse.ok("OK", "Robot zatrzymany. " + " ".join(descriptions))
