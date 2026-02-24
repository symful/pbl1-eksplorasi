import os
import sys
from tkinter import ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from calc.calc import definite_integral, derivative, evaluate
from history.history import (
    add_entry,
    clear_history,
    delete_variable,
    get_history,
    list_variables,
    memory_add,
    memory_clear,
    memory_recall,
    memory_sub,
    set_variable,
)
from settings.settings import DEFAULT_ANGLE_MODE, get_theme
from ui.ui import CalculatorUI

_angle_mode = DEFAULT_ANGLE_MODE
_current_expr = ""
_last_answer = "0"
_current_theme_raw = get_theme("dark")


def _build_ui_theme(src):
    ui = {
        "bg": src.get("bg"),
        "panel": src.get("display_bg"),
        "surface": src.get("btn_bg"),
        "surface2": src.get("btn_op_bg") or src.get("btn_func_bg"),
        "text": src.get("fg"),
        "subtext": src.get("display_fg") or src.get("fg"),
        "blue": src.get("btn_op_bg"),
        "green": src.get("btn_eq_bg"),
        "red": src.get("btn_clear_bg"),
        "teal": src.get("btn_func_bg"),
        "mauve": src.get("btn_func_bg"),
        "peach": src.get("btn_clear_bg"),
        "_raw": src,
    }
    return ui


_ui_theme = _build_ui_theme(_current_theme_raw)


def _get_variables():
    return {k: v for k, v in list_variables().items()}


def _safe_eval(expr, app):
    global _last_answer
    vars_ = _get_variables()
    try:
        result = evaluate(expr, _angle_mode, variables=vars_)
        formatted = f"{result:g}"
        add_entry(expr, formatted)
        app.refresh_history(get_history())
        _last_answer = formatted
        return formatted, True
    except ValueError as err:
        return str(err), False


def _auto_graph(app, expr):
    if "x" not in expr:
        return
    ax, canvas = app.get_graph_objects()
    if ax is None:
        return
    x_min, x_max = app.get_x_range()
    from graph.graph import update_plot

    update_plot(
        ax, canvas, expr, x_min, x_max, _get_variables(), theme=_current_theme_raw
    )


def handle_button(label, app):
    global _current_expr, _angle_mode

    if label == "AC":
        _current_expr = ""
        app.update_display("0", "")

    elif label == "DEL":
        _current_expr = _current_expr[:-1]
        app.update_display(_current_expr or "0", "")

    elif label == "DEG":
        _angle_mode = "RAD" if _angle_mode == "DEG" else "DEG"
        app.set_angle_mode(_angle_mode)
        return

    elif label == "=":
        if not _current_expr:
            return
        formatted, ok = _safe_eval(_current_expr, app)
        if ok:
            app.update_display(formatted, _current_expr + " =")
            _auto_graph(app, _current_expr)
            _current_expr = formatted
        else:
            app.update_display("Error", formatted)
            _current_expr = ""

    elif label == "ANS":
        _current_expr += _last_answer
        app.update_display(_current_expr, "")

    elif label == "__PLOT__":
        ax, canvas = app.get_graph_objects()
        x_min, x_max = app.get_x_range()
        from graph.graph import update_plot

        update_plot(
            ax,
            canvas,
            _current_expr,
            x_min,
            x_max,
            _get_variables(),
            theme=_current_theme_raw,
        )
        return

    elif label == "d/dx":
        if not _current_expr:
            return
        from tkinter import simpledialog

        x_val = simpledialog.askfloat(
            "Derivative", "Evaluate d/dx at x =", initialvalue=0.0
        )
        if x_val is None:
            return
        try:
            vars_ = _get_variables()
            result = derivative(_current_expr, x_val, _angle_mode, vars_)
            formatted = f"{result:g}"
            add_entry(f"d/dx({_current_expr}) at x={x_val}", formatted)
            app.update_display(formatted, f"d/dx({_current_expr})|x={x_val} =")
            app.refresh_history(get_history())
            _current_expr = formatted
        except ValueError as err:
            app.update_display("Error", str(err))
            _current_expr = ""
        return

    elif label == "∫dx":
        if not _current_expr:
            return
        from tkinter import simpledialog

        a = simpledialog.askfloat("Integral", "Lower bound a =", initialvalue=-1.0)
        if a is None:
            return
        b = simpledialog.askfloat("Integral", "Upper bound b =", initialvalue=1.0)
        if b is None:
            return
        try:
            vars_ = _get_variables()
            result = definite_integral(_current_expr, a, b, _angle_mode, vars_)
            formatted = f"{result:g}"
            add_entry(f"∫({_current_expr})dx [{a},{b}]", formatted)
            app.update_display(formatted, f"∫({_current_expr})dx [{a},{b}] =")
            app.refresh_history(get_history())
            _current_expr = formatted
        except ValueError as err:
            app.update_display("Error", str(err))
            _current_expr = ""
        return

    elif label == "M+":
        try:
            val = float(
                evaluate(_current_expr, _angle_mode, _get_variables())
                if _current_expr
                else _last_answer
            )
            memory_add(val)
            app.update_memory_label(memory_recall())
        except Exception:
            pass
        return

    elif label == "M-":
        try:
            val = float(
                evaluate(_current_expr, _angle_mode, _get_variables())
                if _current_expr
                else _last_answer
            )
            memory_sub(val)
            app.update_memory_label(memory_recall())
        except Exception:
            pass
        return

    elif label == "MR":
        mem = memory_recall()
        _current_expr += f"{mem:g}"
        app.update_display(_current_expr, "")
        return

    elif label == "MC":
        memory_clear()
        app.update_memory_label(0.0)
        return

    elif label == "__SETVAR__":
        name, val_str = app.get_var_input()
        if not name:
            return
        try:
            val = evaluate(val_str, _angle_mode, _get_variables()) if val_str else 0.0
            set_variable(name, val)
            app.refresh_variables(list_variables())
        except Exception:
            pass
        return

    elif label == "__DELVAR__":
        name = app.get_selected_var_name()
        if name:
            delete_variable(name)
            app.refresh_variables(list_variables())
        return

    elif label == "__CLRHIST__":
        clear_history()
        app.refresh_history([])
        return

    elif label == "x!":
        _current_expr += "factorial("
        app.update_display(_current_expr, "")

    elif label == "^":
        _current_expr += "**"
        app.update_display(_current_expr, "")

    elif label == "π":
        _current_expr += "pi"
        app.update_display(_current_expr, "")

    elif label == "e":
        _current_expr += "e"
        app.update_display(_current_expr, "")

    elif label == "EE":
        _current_expr += "e+"
        app.update_display(_current_expr, "")

    elif label == "%":
        _current_expr += "%"
        app.update_display(_current_expr, "")

    elif label == "√":
        _current_expr += "sqrt("
        app.update_display(_current_expr, "")

    elif label in {"sin", "cos", "tan", "asin", "acos", "atan", "log", "ln", "exp"}:
        _current_expr += label + "("
        app.update_display(_current_expr, "")

    elif label == "x":
        _current_expr += "x"
        app.update_display(_current_expr, "")

    else:
        _current_expr += label
        app.update_display(_current_expr, "")

    if "x" in _current_expr and label not in {"=", "DEL", "AC"}:
        _auto_graph(app, _current_expr)


def main():
    app = CalculatorUI(theme=_ui_theme)
    try:
        style = ttk.Style()
        style.theme_use("clam")
    except Exception:
        pass
    app.update_theme(_ui_theme)

    try:
        ax, canvas = app.get_graph_objects()
        if ax is not None and canvas is not None:
            from graph.graph import update_plot

            x_min, x_max = app.get_x_range()
            try:
                update_plot(
                    ax,
                    canvas,
                    "0",
                    int(x_min),
                    int(x_max),
                    _get_variables(),
                    theme=_current_theme_raw,
                )
            except Exception:
                pass
    except Exception:
        pass

    app.on_button_press(lambda label: handle_button(label, app))
    app.mainloop()


if __name__ == "__main__":
    main()
