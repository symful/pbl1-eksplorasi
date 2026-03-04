import math

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

matplotlib.use("TkAgg")


def _resolve(theme=None):
    # Allow calls without a theme (e.g. during initial UI construction)
    theme = theme or {}
    return {
        "fig_bg": theme.get("bg", "#11111b"),
        "ax_bg": theme.get("display_bg", "#0b0f1a"),
        "line": theme.get("btn_op_bg", "#89b4fa"),
        "zero": theme.get("btn_bg", "#313244"),
        "grid": theme.get("btn_bg", "#313244"),
        "text": theme.get("fg", "#cdd6f4"),
        "tick": theme.get("display_fg", "#a6adc8"),
        "spine": theme.get("btn_bg", "#313244"),
    }


def _style(fig, ax, theme=None):
    c = _resolve(theme)
    fig.patch.set_facecolor(c["fig_bg"])
    ax.set_facecolor(c["ax_bg"])
    ax.tick_params(colors=c["tick"], labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor(c["spine"])
    ax.grid(True, color=c["grid"], linestyle="--", linewidth=0.4, alpha=0.7)
    ax.axhline(0, color=c["zero"], linewidth=0.8)
    ax.axvline(0, color=c["zero"], linewidth=0.8)
    ax.set_xlabel("x", color=c["tick"], fontsize=8)
    ax.set_ylabel("f(x)", color=c["tick"], fontsize=8)


def _make_ns(x):
    return {
        "sin": np.sin,
        "cos": np.cos,
        "tan": np.tan,
        "arcsin": np.arcsin,
        "arccos": np.arccos,
        "arctan": np.arctan,
        "asin": np.arcsin,
        "acos": np.arccos,
        "atan": np.arctan,
        "sqrt": np.sqrt,
        "log": np.log10,
        "ln": np.log,
        "exp": np.exp,
        "abs": np.abs,
        "pi": math.pi,
        "e": math.e,
        "x": x,
    }


def create_figure(figsize=(4, 2.8)):
    fig, ax = plt.subplots(figsize=figsize)
    fig.subplots_adjust(left=0.12, right=0.97, top=0.92, bottom=0.15)
    _style(fig, ax)
    ax.set_title("Graph", color="#cdd6f4", fontsize=9, pad=6)
    return fig, ax


def update_plot(ax, canvas, expr, x_min=-10, x_max=10, variables=None, theme=None):
    c = _resolve(theme)
    ax.cla()
    _style(ax.get_figure(), ax, theme)
    x = np.linspace(x_min, x_max, 1000)
    ns = _make_ns(x)
    if variables:
        ns.update({k: v for k, v in variables.items() if k != "x"})
    try:
        with np.errstate(divide="ignore", invalid="ignore"):
            y = eval(expr, {"__builtins__": {}}, ns)
        y = np.where(np.abs(y) > 1e8, np.nan, y)
        ax.plot(x, y, color=c["line"], linewidth=1.8)
        ax.set_title(f"f(x) = {expr}", color=c["text"], fontsize=8, pad=4)
    except Exception as err:
        ax.set_title(f"Error: {err}", color="#f38ba8", fontsize=8, pad=4)
    canvas.draw()


def plot_function(expr, x_min=-10, x_max=10):
    x = np.linspace(x_min, x_max, 1000)
    ns = _make_ns(x)
    try:
        with np.errstate(divide="ignore", invalid="ignore"):
            y = eval(expr, {"__builtins__": {}}, ns)
        y = np.where(np.abs(y) > 1e8, np.nan, y)
    except Exception as err:
        raise ValueError(f"Cannot evaluate expression: {err}")
    fig, ax = plt.subplots(figsize=(8, 5))
    _style(fig, ax)
    ax.plot(x, y, color="#89b4fa", linewidth=2)
    ax.set_title(f"f(x) = {expr}", color="#cdd6f4", fontsize=12)
    plt.tight_layout()
    plt.show()
