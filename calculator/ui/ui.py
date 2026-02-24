import tkinter as tk
from tkinter import ttk, font as tkfont
import matplotlib

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

_C = {
    "bg": "#1e1e2e",
    "panel": "#181825",
    "surface": "#313244",
    "surface2": "#45475a",
    "text": "#cdd6f4",
    "subtext": "#6c7086",
    "blue": "#89b4fa",
    "green": "#a6e3a1",
    "red": "#f38ba8",
    "teal": "#89dceb",
    "yellow": "#f9e2af",
    "mauve": "#cba6f7",
    "peach": "#fab387",
}

_LAYOUT = [
    [
        ("DEG", "mode"),
        ("(", "paren"),
        (")", "paren"),
        ("AC", "clear"),
        ("DEL", "clear"),
    ],
    [
        ("sin", "func"),
        ("cos", "func"),
        ("tan", "func"),
        ("asin", "func"),
        ("atan", "func"),
    ],
    [("√", "func"), ("ln", "func"), ("log", "func"), ("x!", "func"), ("^", "op")],
    [("π", "const"), ("e", "const"), ("x", "const"), ("ANS", "const"), ("%", "op")],
    [("7", "num"), ("8", "num"), ("9", "num"), ("/", "op"), ("d/dx", "calc")],
    [("4", "num"), ("5", "num"), ("6", "num"), ("*", "op"), ("∫dx", "calc")],
    [("1", "num"), ("2", "num"), ("3", "num"), ("-", "op"), ("M+", "mem")],
    [("0", "num"), (".", "num"), ("EE", "const"), ("+", "op"), ("=", "equals")],
]

_CAT_COLOR = {
    "mode": (_C["surface2"], _C["text"]),
    "paren": (_C["surface"], _C["teal"]),
    "clear": (_C["red"], _C["bg"]),
    "func": (_C["surface"], _C["teal"]),
    "op": (_C["surface"], _C["blue"]),
    "const": (_C["surface"], _C["mauve"]),
    "num": (_C["surface"], _C["text"]),
    "calc": (_C["surface"], _C["yellow"]),
    "mem": (_C["surface"], _C["peach"]),
    "equals": (_C["green"], _C["bg"]),
}


class CalculatorUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Scientific Calculator")
        self.configure(bg=_C["bg"])
        self.resizable(False, False)

        self._callback = None
        self._angle_var = tk.StringVar(value="DEG")
        self._expr_var = tk.StringVar(value="")
        self._result_var = tk.StringVar(value="0")

        self._fig = None
        self._ax = None
        self._graph_canvas = None

        self._mem_label = None
        self._hist_list = None
        self._var_list = None

        container = tk.Frame(self, bg=_C["bg"])
        container.pack(padx=10, pady=10)

        self._build_left(container)
        self._build_right(container)

    def _build_left(self, parent):
        left = tk.Frame(parent, bg=_C["bg"])
        left.grid(row=0, column=0, padx=(0, 8))

        self._build_display(left)
        self._build_keypad(left)

    def _build_display(self, parent):
        disp = tk.Frame(parent, bg=_C["panel"], padx=12, pady=8)
        disp.pack(fill="x", pady=(0, 6))

        top_row = tk.Frame(disp, bg=_C["panel"])
        top_row.pack(fill="x")

        tk.Label(
            top_row,
            textvariable=self._angle_var,
            font=tkfont.Font(family="Consolas", size=9, weight="bold"),
            bg=_C["surface"],
            fg=_C["blue"],
            padx=6,
            pady=1,
        ).pack(side="left")

        self._status_label = tk.Label(
            top_row,
            text="",
            font=tkfont.Font(family="Consolas", size=9),
            bg=_C["panel"],
            fg=_C["subtext"],
        )
        self._status_label.pack(side="right")

        tk.Label(
            disp,
            textvariable=self._expr_var,
            font=tkfont.Font(family="Consolas", size=10),
            bg=_C["panel"],
            fg=_C["subtext"],
            anchor="e",
            width=30,
        ).pack(fill="x", pady=(4, 0))

        tk.Label(
            disp,
            textvariable=self._result_var,
            font=tkfont.Font(family="Consolas", size=24, weight="bold"),
            bg=_C["panel"],
            fg=_C["text"],
            anchor="e",
            width=30,
        ).pack(fill="x")

    def _build_keypad(self, parent):
        pad = tk.Frame(parent, bg=_C["bg"])
        pad.pack()

        btn_font = tkfont.Font(family="Consolas", size=11)

        for r, row in enumerate(_LAYOUT):
            for c, (label, cat) in enumerate(row):
                bg, fg = _CAT_COLOR.get(cat, (_C["surface"], _C["text"]))
                btn = tk.Button(
                    pad,
                    text=label,
                    font=btn_font,
                    bg=bg,
                    fg=fg,
                    activebackground=_C["surface2"],
                    activeforeground=_C["text"],
                    relief="flat",
                    cursor="hand2",
                    width=5,
                    height=2,
                    command=lambda label=label: self._handle(label),
                )
                btn.grid(row=r, column=c, padx=2, pady=2, sticky="nsew")

                btn.bind(
                    "<Enter>", lambda e, b=btn, bg=bg: b.configure(bg=_lighter(bg))
                )
                btn.bind("<Leave>", lambda e, b=btn, bg=bg: b.configure(bg=bg))

    def _build_right(self, parent):
        right = tk.Frame(parent, bg=_C["bg"])
        right.grid(row=0, column=1, sticky="ns")

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Dark.TNotebook", background=_C["bg"], borderwidth=0)
        style.configure(
            "Dark.TNotebook.Tab",
            background=_C["surface"],
            foreground=_C["subtext"],
            padding=[10, 4],
            font=("Consolas", 9),
        )
        style.map(
            "Dark.TNotebook.Tab",
            background=[("selected", _C["surface2"])],
            foreground=[("selected", _C["text"])],
        )

        nb = ttk.Notebook(right, style="Dark.TNotebook", width=300)
        nb.pack(fill="both", expand=True)

        self._build_graph_tab(nb)
        self._build_memory_tab(nb)
        self._build_vars_tab(nb)
        self._build_history_tab(nb)

    def _build_graph_tab(self, nb):
        frame = tk.Frame(nb, bg=_C["panel"])
        nb.add(frame, text=" Graph ")

        from graph.graph import create_figure

        self._fig, self._ax = create_figure(figsize=(4, 2.8))
        self._graph_canvas = FigureCanvasTkAgg(self._fig, master=frame)
        widget = self._graph_canvas.get_tk_widget()
        widget.configure(bg=_C["panel"])
        widget.pack(fill="both", expand=True, padx=4, pady=4)

        ctrl = tk.Frame(frame, bg=_C["panel"])
        ctrl.pack(fill="x", padx=4, pady=(0, 4))

        tk.Label(
            ctrl, text="x:", bg=_C["panel"], fg=_C["subtext"], font=("Consolas", 9)
        ).pack(side="left")

        self._xmin_var = tk.StringVar(value="-10")
        self._xmax_var = tk.StringVar(value="10")
        for var, default in [(self._xmin_var, "-10"), (self._xmax_var, "10")]:
            e = tk.Entry(
                ctrl,
                textvariable=var,
                width=5,
                bg=_C["surface"],
                fg=_C["text"],
                insertbackground=_C["text"],
                relief="flat",
                font=("Consolas", 9),
            )
            e.pack(side="left", padx=2)

        tk.Button(
            ctrl,
            text="Plot",
            font=("Consolas", 9),
            bg=_C["blue"],
            fg=_C["bg"],
            relief="flat",
            padx=6,
            command=self._trigger_plot,
        ).pack(side="left", padx=4)

    def _trigger_plot(self):
        if self._callback:
            self._callback("__PLOT__")

    def _build_memory_tab(self, nb):
        frame = tk.Frame(nb, bg=_C["panel"])
        nb.add(frame, text=" Memory ")

        tk.Label(
            frame,
            text="Memory Register",
            bg=_C["panel"],
            fg=_C["subtext"],
            font=("Consolas", 9),
        ).pack(pady=(8, 2))

        self._mem_label = tk.Label(
            frame,
            text="M = 0",
            bg=_C["surface"],
            fg=_C["peach"],
            font=("Consolas", 16, "bold"),
            padx=10,
            pady=10,
        )
        self._mem_label.pack(fill="x", padx=8, pady=4)

        btn_frame = tk.Frame(frame, bg=_C["panel"])
        btn_frame.pack(pady=4)

        for label, col in [
            ("M+", _C["green"]),
            ("M-", _C["red"]),
            ("MR", _C["blue"]),
            ("MC", _C["subtext"]),
        ]:
            tk.Button(
                btn_frame,
                text=label,
                width=5,
                height=2,
                bg=_C["surface"],
                fg=col,
                font=("Consolas", 11),
                relief="flat",
                cursor="hand2",
                command=lambda label=label: self._handle(label),
            ).pack(side="left", padx=3)

    def _build_vars_tab(self, nb):
        frame = tk.Frame(nb, bg=_C["panel"])
        nb.add(frame, text=" Vars ")

        tk.Label(
            frame,
            text="Variables",
            bg=_C["panel"],
            fg=_C["subtext"],
            font=("Consolas", 9),
        ).pack(pady=(8, 2))

        list_frame = tk.Frame(frame, bg=_C["panel"])
        list_frame.pack(fill="both", expand=True, padx=8)

        sb = tk.Scrollbar(list_frame, bg=_C["surface"])
        self._var_list = tk.Listbox(
            list_frame,
            bg=_C["surface"],
            fg=_C["mauve"],
            font=("Consolas", 10),
            relief="flat",
            selectbackground=_C["surface2"],
            width=28,
            yscrollcommand=sb.set,
        )
        sb.config(command=self._var_list.yview)
        sb.pack(side="right", fill="y")
        self._var_list.pack(fill="both", expand=True)

        ctrl = tk.Frame(frame, bg=_C["panel"])
        ctrl.pack(fill="x", padx=8, pady=4)

        self._var_name = tk.Entry(
            ctrl,
            width=6,
            bg=_C["surface"],
            fg=_C["text"],
            insertbackground=_C["text"],
            relief="flat",
            font=("Consolas", 10),
        )
        self._var_name.insert(0, "a")
        self._var_name.pack(side="left", padx=(0, 2))

        tk.Label(
            ctrl, text="=", bg=_C["panel"], fg=_C["subtext"], font=("Consolas", 10)
        ).pack(side="left")

        self._var_val = tk.Entry(
            ctrl,
            width=8,
            bg=_C["surface"],
            fg=_C["text"],
            insertbackground=_C["text"],
            relief="flat",
            font=("Consolas", 10),
        )
        self._var_val.insert(0, "0")
        self._var_val.pack(side="left", padx=2)

        tk.Button(
            ctrl,
            text="Set",
            font=("Consolas", 9),
            bg=_C["mauve"],
            fg=_C["bg"],
            relief="flat",
            padx=4,
            command=lambda: self._handle("__SETVAR__"),
        ).pack(side="left", padx=2)

        tk.Button(
            ctrl,
            text="Del",
            font=("Consolas", 9),
            bg=_C["red"],
            fg=_C["bg"],
            relief="flat",
            padx=4,
            command=lambda: self._handle("__DELVAR__"),
        ).pack(side="left", padx=2)

    def _build_history_tab(self, nb):
        frame = tk.Frame(nb, bg=_C["panel"])
        nb.add(frame, text=" History ")

        tk.Label(
            frame,
            text="Calculation History",
            bg=_C["panel"],
            fg=_C["subtext"],
            font=("Consolas", 9),
        ).pack(pady=(8, 2))

        list_frame = tk.Frame(frame, bg=_C["panel"])
        list_frame.pack(fill="both", expand=True, padx=8)

        sb = tk.Scrollbar(list_frame, bg=_C["surface"])
        self._hist_list = tk.Listbox(
            list_frame,
            bg=_C["surface"],
            fg=_C["text"],
            font=("Consolas", 9),
            relief="flat",
            selectbackground=_C["surface2"],
            width=28,
            yscrollcommand=sb.set,
        )
        sb.config(command=self._hist_list.yview)
        sb.pack(side="right", fill="y")
        self._hist_list.pack(fill="both", expand=True)

        tk.Button(
            frame,
            text="Clear History",
            font=("Consolas", 9),
            bg=_C["red"],
            fg=_C["bg"],
            relief="flat",
            padx=6,
            command=lambda: self._handle("__CLRHIST__"),
        ).pack(pady=4)

    def _handle(self, label):
        if self._callback:
            self._callback(label)

    def on_button_press(self, callback):
        self._callback = callback

    def update_display(self, result_text, expr_text="", status=""):
        self._result_var.set(result_text)
        self._expr_var.set(expr_text)
        self._status_label.configure(text=status)

    def set_angle_mode(self, mode):
        self._angle_var.set(mode)

    def update_memory_label(self, value):
        if self._mem_label:
            self._mem_label.configure(text=f"M = {value:g}")

    def refresh_history(self, entries):
        if not self._hist_list:
            return
        self._hist_list.delete(0, "end")
        for e in reversed(entries):
            self._hist_list.insert("end", f"  {e['expression']} = {e['result']}")

    def refresh_variables(self, variables):
        if not self._var_list:
            return
        self._var_list.delete(0, "end")
        for name, val in variables.items():
            self._var_list.insert("end", f"  {name} = {val:g}")

    def get_var_input(self):
        return self._var_name.get().strip(), self._var_val.get().strip()

    def get_selected_var_name(self):
        if self._var_list is None:
            return
        sel = self._var_list.curselection()
        if not sel:
            return None
        text = self._var_list.get(sel[0]).strip()
        return text.split("=")[0].strip()

    def get_x_range(self):
        try:
            return float(self._xmin_var.get()), float(self._xmax_var.get())
        except ValueError:
            return -10.0, 10.0

    def get_graph_objects(self):
        return self._ax, self._graph_canvas

    def update_theme(self, theme):
        pass


def _lighter(hex_color, amount=20):
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    r = min(255, r + amount)
    g = min(255, g + amount)
    b = min(255, b + amount)
    return f"#{r:02x}{g:02x}{b:02x}"
