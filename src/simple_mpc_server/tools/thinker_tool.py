import queue
import threading
import tkinter as tk

from loguru import logger
from mcp.server.fastmcp import FastMCP

from simple_mpc_server.core.Atool import ATool
from simple_mpc_server.core.tool_response import ToolResponse


class ThinkerTool(ATool):
    """Narzędzie MCP do zdalnego rysowania na ekranie użytkownika.

    - Użytkownik tylko patrzy na okno; brak przycisków/sterowania po jego stronie.
    - MCP steruje rysowaniem poprzez wywołania narzędzi (linie, czyszczenie, zamknięcie).
    """

    def __init__(self) -> None:
        self._running: bool = False
        self._queue: queue.Queue = queue.Queue()
        self._root: tk.Tk | None = None
        self._canvas: tk.Canvas | None = None
        self._width: int = 280
        self._height: int = 280
        self._history: list = []
        self._redo_stack: list = []

    # --- logika rysowania w osobnym wątku ---
    def _run_ui(self) -> None:
        try:
            width = self._width
            height = self._height

            root = tk.Tk()
            root.title("MCP drawing window")
            self._root = root

            canvas = tk.Canvas(root, width=width, height=height, bg="black", highlightthickness=1)
            canvas.grid(row=0, column=0, padx=10, pady=10)
            self._canvas = canvas

            def process_queue() -> None:
                try:
                    while True:
                        cmd = self._queue.get_nowait()
                        name = cmd[0]
                        if name == "line":
                            _, x0, y0, x1, y1, color, w = cmd
                            canvas.create_line(x0, y0, x1, y1, fill=color, width=w, capstyle=tk.ROUND, smooth=True)
                        elif name == "dashed_line":
                            _, x0, y0, x1, y1, color, w = cmd
                            canvas.create_line(x0, y0, x1, y1, fill=color, width=w, dash=(4, 4))
                        elif name == "dotted_line":
                            _, x0, y0, x1, y1, color, w = cmd
                            canvas.create_line(x0, y0, x1, y1, fill=color, width=w, dash=(1, 2))
                        elif name == "rectangle":
                            _, x0, y0, x1, y1, color, w = cmd
                            canvas.create_rectangle(x0, y0, x1, y1, outline=color, width=w)
                        elif name == "filled_rectangle":
                            _, x0, y0, x1, y1, fill_color, outline_color, w = cmd
                            canvas.create_rectangle(x0, y0, x1, y1, fill=fill_color, outline=outline_color, width=w)
                        elif name == "circle":
                            _, cx, cy, r, color, w = cmd
                            canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline=color, width=w)
                        elif name == "filled_circle":
                            _, cx, cy, r, fill_color, outline_color, w = cmd
                            canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=fill_color, outline=outline_color, width=w)
                        elif name == "ellipse":
                            _, x0, y0, x1, y1, color, w = cmd
                            canvas.create_oval(x0, y0, x1, y1, outline=color, width=w)
                        elif name == "filled_ellipse":
                            _, x0, y0, x1, y1, fill_color, outline_color, w = cmd
                            canvas.create_oval(x0, y0, x1, y1, fill=fill_color, outline=outline_color, width=w)
                        elif name == "polygon":
                            _, points, color, w, fill = cmd
                            if fill:
                                canvas.create_polygon(*points, fill=fill, outline=color, width=w)
                            else:
                                canvas.create_polygon(*points, outline=color, width=w)
                        elif name == "triangle":
                            _, x1, y1, x2, y2, x3, y3, fill_color, outline_color, w = cmd
                            canvas.create_polygon(x1, y1, x2, y2, x3, y3, fill=fill_color, outline=outline_color, width=w)
                        elif name == "star":
                            _, cx, cy, size, color, fill_color = cmd
                            points = []
                            import math
                            for i in range(10):
                                angle = i * math.pi / 5
                                radius = size if i % 2 == 0 else size / 2
                                x = cx + radius * math.cos(angle - math.pi / 2)
                                y = cy + radius * math.sin(angle - math.pi / 2)
                                points.extend([x, y])
                            canvas.create_polygon(*points, fill=fill_color, outline=color, width=2)
                        elif name == "arrow":
                            _, x0, y0, x1, y1, color, w = cmd
                            canvas.create_line(x0, y0, x1, y1, fill=color, width=w, arrow=tk.LAST, arrowshape=(20, 20, 10))
                        elif name == "arc":
                            _, x0, y0, x1, y1, start, extent, color, w = cmd
                            canvas.create_arc(x0, y0, x1, y1, start=start, extent=extent, outline=color, width=w, style=tk.ARC)
                        elif name == "text":
                            _, x, y, text, color, font_size = cmd
                            canvas.create_text(x, y, text=text, fill=color, font=("Arial", font_size))
                        elif name == "background_color":
                            _, bg_color = cmd
                            root.config(bg=bg_color)
                            canvas.config(bg=bg_color)
                        elif name == "clear":
                            canvas.delete("all")
                            self._history.clear()
                            self._redo_stack.clear()
                        elif name == "undo":
                            if self._history:
                                self._redo_stack.append(self._history.pop())
                                canvas.delete("all")
                                for cmd_item in self._history:
                                    self._execute_command(canvas, cmd_item)
                        elif name == "redo":
                            if self._redo_stack:
                                cmd_item = self._redo_stack.pop()
                                self._history.append(cmd_item)
                                self._execute_command(canvas, cmd_item)
                        elif name == "close":
                            root.after(0, root.destroy)
                            return
                except queue.Empty:
                    pass
                root.after(16, process_queue)

            def on_close() -> None:
                self._running = False
                root.destroy()

            root.protocol("WM_DELETE_WINDOW", on_close)
            process_queue()
            root.mainloop()
        except Exception as exc:
            logger.error(f"Błąd w oknie rysowania: {exc}")
        finally:
            self._running = False

    def _execute_command(self, canvas: tk.Canvas, cmd: tuple) -> None:
        """Wykonuje polecenie rysunkowe (używane do undo/redo)."""
        name = cmd[0]
        if name == "line":
            _, x0, y0, x1, y1, color, w = cmd
            canvas.create_line(x0, y0, x1, y1, fill=color, width=w, capstyle=tk.ROUND, smooth=True)
        elif name == "polygon":
            _, points, color, w, fill = cmd
            if fill:
                canvas.create_polygon(*points, fill=fill, outline=color, width=w)
            else:
                canvas.create_polygon(*points, outline=color, width=w)

    # --- rejestracja w MCP ---
    def register(self, mcp: FastMCP) -> None:
        """Rejestruje narzędzia do sterowania rysowaniem."""

        @mcp.tool(name="start_drawing_session")
        def start_drawing_session(width: int = 280, height: int = 280) -> ToolResponse[str]:
            """Uruchamia okno rysowania sterowane przez MCP.

            Parametry:
            - width, height: rozmiar canvasa w pikselach.
            """

            if self._running:
                return ToolResponse.fail("Sesja rysowania jest już uruchomiona.")

            self._width = width
            self._height = height
            self._running = True

            logger.debug("Uruchamianie sesji rysowania (ThinkerTool)")
            thread = threading.Thread(target=self._run_ui, daemon=True)
            thread.start()

            return ToolResponse.ok(
                "Sesja rysowania została uruchomiona.",
                "Na lokalnej maszynie otwarto okno Tkinter z czarnym canvasem.",
            )

        @mcp.tool(name="draw_line")
        def draw_line(
            x0: int,
            y0: int,
            x1: int,
            y1: int,
            color: str = "white",
            width: int = 3,
        ) -> ToolResponse[str]:
            """Rysuje linię na aktualnej sesji rysowania.

            Współrzędne podawane są w pikselach w obrębie canvasa.
            """

            if not self._running:
                return ToolResponse.fail("Sesja rysowania nie jest uruchomiona.")

            self._queue.put(("line", x0, y0, x1, y1, color, width))
            return ToolResponse.ok("Narysowano linię.", f"Linia od ({x0},{y0}) do ({x1},{y1}).")

        @mcp.tool(name="clear_canvas")
        def clear_canvas() -> ToolResponse[str]:
            """Czyści cały canvas (usuwa rysunek)."""

            if not self._running:
                return ToolResponse.fail("Sesja rysowania nie jest uruchomiona.")

            self._queue.put(("clear",))
            return ToolResponse.ok("Wyczyszczono canvas.", "Canvas został wyczyszczony.")

        @mcp.tool(name="draw_rectangle")
        def draw_rectangle(
            x0: int,
            y0: int,
            x1: int,
            y1: int,
            color: str = "white",
            width: int = 1,
        ) -> ToolResponse[str]:
            """Rysuje prostokąt na canvasie."""

            if not self._running:
                return ToolResponse.fail("Sesja rysowania nie jest uruchomiona.")

            self._queue.put(("rectangle", x0, y0, x1, y1, color, width))
            return ToolResponse.ok("Narysowano prostokąt.", f"Prostokąt od ({x0},{y0}) do ({x1},{y1}).")

        @mcp.tool(name="draw_filled_rectangle")
        def draw_filled_rectangle(
            x0: int,
            y0: int,
            x1: int,
            y1: int,
            fill_color: str = "white",
            outline_color: str = "black",
            width: int = 1,
        ) -> ToolResponse[str]:
            """Rysuje wypełniony prostokąt na canvasie."""

            if not self._running:
                return ToolResponse.fail("Sesja rysowania nie jest uruchomiona.")

            self._queue.put(("filled_rectangle", x0, y0, x1, y1, fill_color, outline_color, width))
            return ToolResponse.ok("Narysowano wypełniony prostokąt.", f"Wypełniony prostokąt od ({x0},{y0}) do ({x1},{y1}).")

        @mcp.tool(name="draw_circle")
        def draw_circle(
            cx: int,
            cy: int,
            radius: int,
            color: str = "white",
            width: int = 1,
        ) -> ToolResponse[str]:
            """Rysuje koło na canvasie.

            Parametry:
            - cx, cy: współrzędne środka.
            - radius: promień koła.
            """

            if not self._running:
                return ToolResponse.fail("Sesja rysowania nie jest uruchomiona.")

            self._queue.put(("circle", cx, cy, radius, color, width))
            return ToolResponse.ok("Narysowano koło.", f"Koło ze środkiem ({cx},{cy}) i promieniem {radius}.")

        @mcp.tool(name="draw_filled_circle")
        def draw_filled_circle(
            cx: int,
            cy: int,
            radius: int,
            fill_color: str = "white",
            outline_color: str = "black",
            width: int = 1,
        ) -> ToolResponse[str]:
            """Rysuje wypełnione koło na canvasie."""

            if not self._running:
                return ToolResponse.fail("Sesja rysowania nie jest uruchomiona.")

            self._queue.put(("filled_circle", cx, cy, radius, fill_color, outline_color, width))
            return ToolResponse.ok("Narysowano wypełnione koło.", f"Wypełnione koło ze środkiem ({cx},{cy}) i promieniem {radius}.")

        @mcp.tool(name="draw_polygon")
        def draw_polygon(
            points: list[int],
            color: str = "white",
            width: int = 1,
            fill_color: str | None = None,
        ) -> ToolResponse[str]:
            """Rysuje wielokąt na canvasie.

            Parametry:
            - points: lista współrzędnych [x1, y1, x2, y2, ...].
            - fill_color: kolor wypełnienia (None = bez wypełnienia).
            """

            if not self._running:
                return ToolResponse.fail("Sesja rysowania nie jest uruchomiona.")

            self._queue.put(("polygon", points, color, width, fill_color))
            return ToolResponse.ok("Narysowano wielokąt.", f"Wielokąt z {len(points)//2} wierzchołkami.")

        @mcp.tool(name="draw_text")
        def draw_text(
            x: int,
            y: int,
            text: str,
            color: str = "white",
            font_size: int = 12,
        ) -> ToolResponse[str]:
            """Rysuje tekst na canvasie."""

            if not self._running:
                return ToolResponse.fail("Sesja rysowania nie jest uruchomiona.")

            self._queue.put(("text", x, y, text, color, font_size))
            return ToolResponse.ok("Narysowano tekst.", f"Tekst '{text}' w pozycji ({x},{y}).")

        @mcp.tool(name="draw_dashed_line")
        def draw_dashed_line(
            x0: int,
            y0: int,
            x1: int,
            y1: int,
            color: str = "white",
            width: int = 3,
        ) -> ToolResponse[str]:
            """Rysuje przerywaną linię na canvasie."""

            if not self._running:
                return ToolResponse.fail("Sesja rysowania nie jest uruchomiona.")

            self._queue.put(("dashed_line", x0, y0, x1, y1, color, width))
            return ToolResponse.ok("Narysowano przerywaną linię.", f"Linia od ({x0},{y0}) do ({x1},{y1}).")

        @mcp.tool(name="draw_dotted_line")
        def draw_dotted_line(
            x0: int,
            y0: int,
            x1: int,
            y1: int,
            color: str = "white",
            width: int = 3,
        ) -> ToolResponse[str]:
            """Rysuje linię kropkowaną na canvasie."""

            if not self._running:
                return ToolResponse.fail("Sesja rysowania nie jest uruchomiona.")

            self._queue.put(("dotted_line", x0, y0, x1, y1, color, width))
            return ToolResponse.ok("Narysowano linię kropkowaną.", f"Linia od ({x0},{y0}) do ({x1},{y1}).")

        @mcp.tool(name="draw_ellipse")
        def draw_ellipse(
            x0: int,
            y0: int,
            x1: int,
            y1: int,
            color: str = "white",
            width: int = 1,
        ) -> ToolResponse[str]:
            """Rysuje elipsę na canvasie."""

            if not self._running:
                return ToolResponse.fail("Sesja rysowania nie jest uruchomiona.")

            self._queue.put(("ellipse", x0, y0, x1, y1, color, width))
            return ToolResponse.ok("Narysowano elipsę.", f"Elipsa w obszarze ({x0},{y0}) do ({x1},{y1}).")

        @mcp.tool(name="draw_filled_ellipse")
        def draw_filled_ellipse(
            x0: int,
            y0: int,
            x1: int,
            y1: int,
            fill_color: str = "white",
            outline_color: str = "black",
            width: int = 1,
        ) -> ToolResponse[str]:
            """Rysuje wypełnioną elipsę na canvasie."""

            if not self._running:
                return ToolResponse.fail("Sesja rysowania nie jest uruchomiona.")

            self._queue.put(("filled_ellipse", x0, y0, x1, y1, fill_color, outline_color, width))
            return ToolResponse.ok("Narysowano wypełnioną elipsę.", f"Elipsa w obszarze ({x0},{y0}) do ({x1},{y1}).")

        @mcp.tool(name="draw_triangle")
        def draw_triangle(
            x1: int,
            y1: int,
            x2: int,
            y2: int,
            x3: int,
            y3: int,
            fill_color: str = "white",
            outline_color: str = "black",
            width: int = 1,
        ) -> ToolResponse[str]:
            """Rysuje trójkąt na canvasie."""

            if not self._running:
                return ToolResponse.fail("Sesja rysowania nie jest uruchomiona.")

            self._queue.put(("triangle", x1, y1, x2, y2, x3, y3, fill_color, outline_color, width))
            return ToolResponse.ok("Narysowano trójkąt.", f"Trójkąt z wierzchołkami ({x1},{y1}), ({x2},{y2}), ({x3},{y3}).")

        @mcp.tool(name="draw_star")
        def draw_star(
            cx: int,
            cy: int,
            size: int,
            color: str = "white",
            fill_color: str = "yellow",
        ) -> ToolResponse[str]:
            """Rysuje gwiazdę na canvasie."""

            if not self._running:
                return ToolResponse.fail("Sesja rysowania nie jest uruchomiona.")

            self._queue.put(("star", cx, cy, size, color, fill_color))
            return ToolResponse.ok("Narysowano gwiazdę.", f"Gwiazda ze środkiem ({cx},{cy}) i rozmiarem {size}.")

        @mcp.tool(name="draw_arrow")
        def draw_arrow(
            x0: int,
            y0: int,
            x1: int,
            y1: int,
            color: str = "white",
            width: int = 3,
        ) -> ToolResponse[str]:
            """Rysuje strzałkę na canvasie."""

            if not self._running:
                return ToolResponse.fail("Sesja rysowania nie jest uruchomiona.")

            self._queue.put(("arrow", x0, y0, x1, y1, color, width))
            return ToolResponse.ok("Narysowano strzałkę.", f"Strzałka od ({x0},{y0}) do ({x1},{y1}).")

        @mcp.tool(name="draw_arc")
        def draw_arc(
            x0: int,
            y0: int,
            x1: int,
            y1: int,
            start: int = 0,
            extent: int = 90,
            color: str = "white",
            width: int = 1,
        ) -> ToolResponse[str]:
            """Rysuje łuk na canvasie.

            Parametry:
            - start: kąt początkowy w stopniach.
            - extent: kąt rozciągnięcia w stopniach.
            """

            if not self._running:
                return ToolResponse.fail("Sesja rysowania nie jest uruchomiona.")

            self._queue.put(("arc", x0, y0, x1, y1, start, extent, color, width))
            return ToolResponse.ok("Narysowano łuk.", f"Łuk w obszarze ({x0},{y0}) do ({x1},{y1}).")

        @mcp.tool(name="set_background_color")
        def set_background_color(color: str = "black") -> ToolResponse[str]:
            """Zmienia kolor tła canvasa."""

            if not self._running:
                return ToolResponse.fail("Sesja rysowania nie jest uruchomiona.")

            self._queue.put(("background_color", color))
            return ToolResponse.ok("Zmieniono kolor tła.", f"Kolor tła zmieniony na {color}.")

        @mcp.tool(name="undo")
        def undo() -> ToolResponse[str]:
            """Cofa ostatnią akcję rysunku."""

            if not self._running:
                return ToolResponse.fail("Sesja rysowania nie jest uruchomiona.")

            self._queue.put(("undo",))
            return ToolResponse.ok("Cofnięto akcję.", "Ostatnia akcja została cofnięta.")

        @mcp.tool(name="redo")
        def redo() -> ToolResponse[str]:
            """Ponawia ostatnią cofniętą akcję."""

            if not self._running:
                return ToolResponse.fail("Sesja rysowania nie jest uruchomiona.")

            self._queue.put(("redo",))
            return ToolResponse.ok("Ponowiono akcję.", "Ostatnia cofnięta akcja została ponowiona.")

        @mcp.tool(name="stop_drawing_session")
        def stop_drawing_session() -> ToolResponse[str]:
            """Zamyka okno rysowania i kończy sesję."""

            if not self._running:
                return ToolResponse.fail("Sesja rysowania nie jest uruchomiona.")

            self._queue.put(("close",))
            return ToolResponse.ok("Zamykanie okna rysowania.", "Sesja rysowania zostanie zakończona.")

#ToDo: Naprawić zamyaknie sesji oraz bład Tcl_AsyncDelete: async handler deleted by the wrong thread
