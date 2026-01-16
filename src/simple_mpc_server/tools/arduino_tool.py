import time

from loguru import logger
from mcp.server.fastmcp import FastMCP

from simple_mpc_server.core.Atool import ATool
from simple_mpc_server.core.arduino_board import ArduinoBoard
from simple_mpc_server.core.tool_response import ToolResponse


class ArduinoTool(ATool):
    """Narzędzie MCP do rysowania na macierzy LED Arduino UNO R4.

    Komunikuje się z płytką przez klasę ArduinoBoard, wysyłając proste
    komendy tekstowe rozumiane przez szkic na UNO R4:

    - "clear" – czyści macierz
    - "line x0 y0 x1 y1" – rysuje linię na macierzy LED
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
            return False, "Port nie został ustawiony. Wywołaj najpierw narzędzie 'arduino_connect'."

        logger.debug(f"Próba połączenia z Arduino na porcie {self._port} ({self._baudrate} bps)")
        board = ArduinoBoard(self._port, self._baudrate)
        if not board.connect():
            return False, f"Nie udało się połączyć z Arduino na porcie {self._port}."

        self._board = board
        return True, ""

    def register(self, mcp: FastMCP) -> None:
        """Rejestruje narzędzia do sterowania macierzą LED UNO R4."""

        @mcp.tool(name="arduino_connect")
        def arduino_connect(port: str, baudrate: int = 115200) -> ToolResponse[str]:
            """Nawiązuje połączenie z płytką Arduino.

            Parametry:
            - port: np. "COM4" na Windows
            - baudrate: domyślnie 115200 (tak jak w szkicu UNO R4)
            """

            self._port = port
            self._baudrate = baudrate

            logger.debug(f"Łączenie z Arduino na porcie {port} ({baudrate} bps)")
            board = ArduinoBoard(port, baudrate)
            if not board.connect():
                logger.error(f"Nie udało się połączyć z Arduino na porcie {port}")
                self._board = None
                return ToolResponse.fail(f"Nie udało się połączyć z Arduino na porcie {port}.")

            self._board = board
            return ToolResponse.ok(
                f"Połączono z Arduino na porcie {port}.",
                f"Połączono z Arduino UNO R4 ({port}, {baudrate} bps).",
            )

        @mcp.tool(name="arduino_disconnect")
        def arduino_disconnect() -> ToolResponse[str]:
            """Rozłącza aktualne połączenie z Arduino."""

            if not self._board or not self._board.is_connected():
                return ToolResponse.fail("Brak aktywnego połączenia z Arduino.")

            try:
                self._board.disconnect()
                self._board = None
                return ToolResponse.ok("Rozłączono z Arduino.", "Połączenie UART zostało zamknięte.")
            except Exception as exc:  # pragma: no cover - zabezpieczenie na niespodziewany błąd
                logger.error(f"Błąd podczas rozłączania z Arduino: {exc}")
                return ToolResponse.fail("Wystąpił błąd podczas rozłączania z Arduino.")

        @mcp.tool(name="arduino_clear")
        def arduino_clear() -> ToolResponse[str]:
            """Czyści macierz LED na UNO R4 (komenda "clear")."""

            ok, msg = self._ensure_connected()
            if not ok:
                logger.error(msg)
                return ToolResponse.fail(msg)

            assert self._board is not None

            if not self._board.send_command("clear"):
                return ToolResponse.fail("Nie udało się wysłać komendy 'clear' do Arduino.")

            time.sleep(0.05)
            response = self._board.read_response()
            if response and response.startswith("OK"):
                return ToolResponse.ok("OK", "Macierz LED została wyczyszczona.")

            return ToolResponse.fail(f"Nieprawidłowa odpowiedź z Arduino: {response or 'brak odpowiedzi'}")

        @mcp.tool(name="arduino_draw_line")
        def arduino_draw_line(
            x0: int,
            y0: int,
            x1: int,
            y1: int,
        ) -> ToolResponse[str]:
            """Rysuje linię na macierzy LED UNO R4.

            Współrzędne odpowiadają polom macierzy LED (UNO R4 ma
            macierz 12x8, więc typowo x = 0..11, y = 0..7).
            """

            ok, msg = self._ensure_connected()
            if not ok:
                logger.error(msg)
                return ToolResponse.fail(msg)

            assert self._board is not None

            command = f"line {x0} {y0} {x1} {y1}"
            logger.debug(f"Wysyłanie komendy do Arduino: {command}")
            if not self._board.send_command(command):
                return ToolResponse.fail("Nie udało się wysłać komendy 'line' do Arduino.")

            time.sleep(0.05)
            response = self._board.read_response()
            if response and response.startswith("OK"):
                return ToolResponse.ok(
                    "OK",
                    f"Narysowano linię na macierzy: ({x0},{y0}) -> ({x1},{y1}).",
                )

            return ToolResponse.fail(f"Nieprawidłowa odpowiedź z Arduino: {response or 'brak odpowiedzi'}")
