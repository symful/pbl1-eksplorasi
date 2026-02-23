DEFAULT_ANGLE_MODE = "deg"

THEMES = {
    "dark": {
        "bg": "#1e1e2e",
        "fg": "#cdd6f4",
        "display_bg": "#181825",
        "display_fg": "#cdd6f4",
        "btn_bg": "#313244",
        "btn_fg": "#cdd6f4",
        "btn_op_bg": "#89b4fa",
        "btn_op_fg": "#1e1e2e",
        "btn_eq_bg": "#a6e3a1",
        "btn_eq_fg": "#1e1e2e",
        "btn_func_bg": "#89dceb",
        "btn_func_fg": "#1e1e2e",
        "btn_clear_bg": "#f38ba8",
        "btn_clear_fg": "#1e1e2e",
    },
}


def get_theme(name):
    return THEMES.get(name, THEMES["dark"])
