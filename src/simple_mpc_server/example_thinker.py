import tkinter as tk


def main():
    size = 280
    brush = 18

    root = tk.Tk()
    root.title("Proste rysowanie (b)")

    canvas = tk.Canvas(root, width=size, height=size, bg="black", highlightthickness=1)
    canvas.grid(row=0, column=0, columnspan=3, padx=10, pady=10)

    status_var = tk.StringVar(value=f"Pędzel: {brush}px")
    tk.Label(root, textvariable=status_var, font=("Segoe UI", 10)).grid(row=1, column=0, columnspan=3, pady=(0, 8))

    state = {"last": None, "brush": brush}

    def on_down(e):
        state["last"] = (e.x, e.y)

    def on_move(e):
        if state["last"] is None:
            return
        x0, y0 = state["last"]
        x1, y1 = e.x, e.y
        canvas.create_line(x0, y0, x1, y1, fill="white", width=state["brush"], capstyle=tk.ROUND, smooth=True)
        state["last"] = (x1, y1)

    def on_up(e):
        state["last"] = None

    canvas.bind("<ButtonPress-1>", on_down)
    canvas.bind("<B1-Motion>", on_move)
    canvas.bind("<ButtonRelease-1>", on_up)

    def clear():
        canvas.delete("all")

    def thicker():
        if state["brush"] < 48:
            state["brush"] += 2
            status_var.set(f"Pędzel: {state['brush']}px")

    def thinner():
        if state["brush"] > 2:
            state["brush"] -= 2
            status_var.set(f"Pędzel: {state['brush']}px")

    tk.Button(root, text="Wyczyść", command=clear).grid(row=2, column=0, padx=6, pady=8, sticky="ew")
    tk.Button(root, text="Grubszy pędzel", command=thicker).grid(row=2, column=1, padx=6, pady=8, sticky="ew")
    tk.Button(root, text="Cieńszy pędzel", command=thinner).grid(row=2, column=2, padx=6, pady=8, sticky="ew")

    root.mainloop()


if __name__ == "__main__":
    main()
