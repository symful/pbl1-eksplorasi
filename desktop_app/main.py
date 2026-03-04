from __future__ import annotations

import json
import os
import sys
import threading
import tkinter as tk
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, List, Optional, Tuple

# Ensure we can import from project root
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
sys.path.insert(0, _PROJECT_ROOT)

# --- Import scraping pipeline (economic calendar) ---
try:
    from scrape.main import run_pipeline  # type: ignore
except Exception as exc:  # pragma: no cover
    raise SystemExit(
        "Cannot import `scrape.main.run_pipeline`. "
        "Run this from the project root and ensure dependencies are installed."
    ) from exc

# --- Import price scraper (yfinance) ---
try:
    from scrape.scrapers.yfinance_price_scraper import (  # type: ignore
        QuoteSnapshot,
        YahooFinancePriceScraper,
    )
except Exception as exc:  # pragma: no cover
    raise SystemExit(
        "Cannot import yfinance price scraper. "
        "Ensure `yfinance` is installed in the same environment."
    ) from exc


# ============================================================
# Simple dark theme (ttk + tk widgets)
# ============================================================

C = {
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


# ============================================================
# Shared helpers
# ============================================================


def _utc_now_rfc3339() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_int(s: str, default: int) -> int:
    try:
        return int(str(s).strip())
    except Exception:
        return default


def _parse_date_yyyy_mm_dd(s: str) -> Optional[str]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return s
    except Exception:
        return None


def _pretty_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def _treeview_clear(tv: ttk.Treeview) -> None:
    for iid in tv.get_children():
        tv.delete(iid)


def _event_to_dict(e: Any) -> Dict[str, Any]:
    """
    Convert EconomicEvent into a dict safe for JSON.
    We avoid importing the model type directly to keep UI resilient.
    """
    if hasattr(e, "to_dict"):
        return e.to_dict(include_raw=False)  # type: ignore[attr-defined]
    try:
        d = asdict(e)
    except Exception:
        d = dict(e) if isinstance(e, dict) else {"value": str(e)}

    dt = d.get("datetime_utc")
    if isinstance(dt, datetime):
        d["datetime_utc"] = dt.isoformat()
    return d


# ============================================================
# Pure Tkinter Canvas line chart
# ============================================================


class CanvasLineChart(tk.Canvas):
    """
    Minimal line chart using pure Tkinter Canvas.

    - Call `set_series(points)` with points as list of (x, y):
      where x is datetime (or float), y is float.
    - The chart auto-scales.
    """

    def __init__(self, parent: tk.Widget, **kwargs: Any) -> None:
        super().__init__(
            parent,
            bg=C["panel"],
            highlightthickness=1,
            highlightbackground=C["surface2"],
            **kwargs,
        )
        self._points: List[Tuple[datetime, float]] = []
        self._title: str = ""
        self._subtitle: str = ""
        self._y_label: str = "Price"

        self.bind("<Configure>", lambda _e: self._redraw())

    def set_title(self, title: str, subtitle: str = "") -> None:
        self._title = title or ""
        self._subtitle = subtitle or ""
        self._redraw()

    def set_y_label(self, text: str) -> None:
        self._y_label = text or "Value"
        self._redraw()

    def set_series(self, points: List[Tuple[datetime, float]]) -> None:
        self._points = points or []
        self._redraw()

    def clear(self) -> None:
        self._points = []
        self._title = ""
        self._subtitle = ""
        self.delete("all")

    def _redraw(self) -> None:
        self.delete("all")
        w = max(1, int(self.winfo_width()))
        h = max(1, int(self.winfo_height()))

        pad_l = 56
        pad_r = 14
        pad_t = 34
        pad_b = 26

        plot_x0 = pad_l
        plot_y0 = pad_t
        plot_x1 = w - pad_r
        plot_y1 = h - pad_b

        # Background
        self.create_rectangle(0, 0, w, h, fill=C["panel"], outline=C["panel"], width=0)

        # Title
        if self._title:
            self.create_text(
                pad_l,
                12,
                text=self._title,
                fill=C["text"],
                font=("Consolas", 11, "bold"),
                anchor="w",
            )
        if self._subtitle:
            self.create_text(
                pad_l,
                26,
                text=self._subtitle,
                fill=C["subtext"],
                font=("Consolas", 9),
                anchor="w",
            )

        # Plot area border
        self.create_rectangle(
            plot_x0,
            plot_y0,
            plot_x1,
            plot_y1,
            outline=C["surface2"],
            width=1,
        )

        # No data
        if len(self._points) < 2:
            self.create_text(
                (plot_x0 + plot_x1) / 2,
                (plot_y0 + plot_y1) / 2,
                text="No data",
                fill=C["subtext"],
                font=("Consolas", 11),
            )
            return

        # Extract ranges
        xs = [p[0].timestamp() for p in self._points]
        ys = [p[1] for p in self._points]

        x_min = min(xs)
        x_max = max(xs)
        y_min = min(ys)
        y_max = max(ys)

        # Avoid zero range
        if x_max == x_min:
            x_max = x_min + 1
        if y_max == y_min:
            y_max = y_min + 1e-9

        # Add small padding for y-range
        y_pad = (y_max - y_min) * 0.06
        y_min -= y_pad
        y_max += y_pad

        def x_to_px(x_ts: float) -> float:
            return plot_x0 + (x_ts - x_min) * (plot_x1 - plot_x0) / (x_max - x_min)

        def y_to_px(y: float) -> float:
            return plot_y1 - (y - y_min) * (plot_y1 - plot_y0) / (y_max - y_min)

        # Grid (horizontal)
        grid_lines = 4
        for i in range(grid_lines + 1):
            t = i / grid_lines
            yv = y_min + (y_max - y_min) * t
            py = y_to_px(yv)
            self.create_line(
                plot_x0,
                py,
                plot_x1,
                py,
                fill=C["surface"],
                width=1,
                dash=(3, 4),
            )
            self.create_text(
                plot_x0 - 8,
                py,
                text=f"{yv:.4g}",
                fill=C["subtext"],
                font=("Consolas", 8),
                anchor="e",
            )

        # X axis labels: show start/end times (UTC)
        start_dt = datetime.fromtimestamp(x_min, tz=timezone.utc)
        end_dt = datetime.fromtimestamp(x_max, tz=timezone.utc)
        self.create_text(
            plot_x0,
            plot_y1 + 12,
            text=start_dt.strftime("%Y-%m-%d"),
            fill=C["subtext"],
            font=("Consolas", 8),
            anchor="w",
        )
        self.create_text(
            plot_x1,
            plot_y1 + 12,
            text=end_dt.strftime("%Y-%m-%d"),
            fill=C["subtext"],
            font=("Consolas", 8),
            anchor="e",
        )

        # Y label
        self.create_text(
            12,
            (plot_y0 + plot_y1) / 2,
            text=self._y_label,
            fill=C["subtext"],
            font=("Consolas", 9),
            angle=90,
        )

        # Build polyline
        coords: List[float] = []
        for dt, y in self._points:
            xt = dt.timestamp()
            coords.append(x_to_px(xt))
            coords.append(y_to_px(y))

        # Draw line
        self.create_line(*coords, fill=C["blue"], width=2, smooth=False)

        # Draw last-point marker
        last_x = coords[-2]
        last_y = coords[-1]
        self.create_oval(
            last_x - 3,
            last_y - 3,
            last_x + 3,
            last_y + 3,
            fill=C["yellow"],
            outline=C["panel"],
            width=1,
        )

        # Show last value label
        last_val = self._points[-1][1]
        self.create_text(
            plot_x1,
            plot_y0 - 10,
            text=f"Last: {last_val:.6g}",
            fill=C["text"],
            font=("Consolas", 9, "bold"),
            anchor="e",
        )


# ============================================================
# Calendar Tab
# ============================================================


class CalendarTab(ttk.Frame):
    def __init__(self, parent: ttk.Notebook):
        super().__init__(parent)
        self.configure(style="Panel.TFrame")

        self._events: List[Dict[str, Any]] = []
        self._refresh_inflight = False

        self._build_controls()
        self._build_table()
        self._build_json_view()

    def _build_controls(self) -> None:
        top = ttk.Frame(self, style="Panel.TFrame")
        top.pack(fill="x", padx=10, pady=10)

        ttk.Label(top, text="Currency:", style="Panel.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.currency_var = tk.StringVar(value="ALL")
        cur = ttk.Combobox(
            top, textvariable=self.currency_var, state="readonly", width=8
        )
        cur["values"] = ("ALL", "USD", "IDR")
        cur.grid(row=0, column=1, padx=(6, 14), sticky="w")

        ttk.Label(top, text="Impact:", style="Panel.TLabel").grid(
            row=0, column=2, sticky="w"
        )
        self.impact_high = tk.BooleanVar(value=True)
        self.impact_med = tk.BooleanVar(value=True)
        self.impact_low = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="High", variable=self.impact_high).grid(
            row=0, column=3, sticky="w"
        )
        ttk.Checkbutton(top, text="Med", variable=self.impact_med).grid(
            row=0, column=4, sticky="w"
        )
        ttk.Checkbutton(top, text="Low", variable=self.impact_low).grid(
            row=0, column=5, sticky="w"
        )

        ttk.Label(top, text="Days back:", style="Panel.TLabel").grid(
            row=1, column=0, sticky="w", pady=(8, 0)
        )
        self.days_back_var = tk.StringVar(value="1")
        ttk.Entry(top, textvariable=self.days_back_var, width=8).grid(
            row=1, column=1, sticky="w", padx=(6, 14), pady=(8, 0)
        )

        ttk.Label(top, text="Days ahead:", style="Panel.TLabel").grid(
            row=1, column=2, sticky="w", pady=(8, 0)
        )
        self.days_ahead_var = tk.StringVar(value="7")
        ttk.Entry(top, textvariable=self.days_ahead_var, width=8).grid(
            row=1, column=3, sticky="w", padx=(6, 14), pady=(8, 0)
        )

        btns = ttk.Frame(top, style="Panel.TFrame")
        btns.grid(row=0, column=6, rowspan=2, sticky="e", padx=(20, 0))

        self.refresh_btn = ttk.Button(
            btns, text="Refresh Calendar", command=self.refresh_async
        )
        self.refresh_btn.pack(fill="x", pady=(0, 6))

        self.export_btn = ttk.Button(
            btns, text="Export JSON…", command=self.export_json
        )
        self.export_btn.pack(fill="x")

        self.status = ttk.Label(top, text="Ready.", style="Sub.TLabel")
        self.status.grid(row=2, column=0, columnspan=7, sticky="w", pady=(10, 0))

        top.columnconfigure(6, weight=1)

    def _build_table(self) -> None:
        mid = ttk.Frame(self, style="Panel.TFrame")
        mid.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        cols = (
            "date",
            "time",
            "currency",
            "impact",
            "title",
            "source",
            "actual",
            "forecast",
            "previous",
        )
        self.tv = ttk.Treeview(mid, columns=cols, show="headings", height=14)

        headings = {
            "date": "Date",
            "time": "Time",
            "currency": "Cur",
            "impact": "Impact",
            "title": "Title",
            "source": "Source",
            "actual": "Actual",
            "forecast": "Forecast",
            "previous": "Prev",
        }
        widths = {
            "date": 90,
            "time": 70,
            "currency": 50,
            "impact": 70,
            "title": 420,
            "source": 110,
            "actual": 90,
            "forecast": 90,
            "previous": 90,
        }

        for c in cols:
            self.tv.heading(c, text=headings[c])
            self.tv.column(c, width=widths[c], anchor="w")

        vsb = ttk.Scrollbar(mid, orient="vertical", command=self.tv.yview)
        hsb = ttk.Scrollbar(mid, orient="horizontal", command=self.tv.xview)
        self.tv.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tv.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        mid.rowconfigure(0, weight=1)
        mid.columnconfigure(0, weight=1)

        self.tv.bind("<<TreeviewSelect>>", self._on_select_event)

    def _build_json_view(self) -> None:
        bot = ttk.Frame(self, style="Panel.TFrame")
        bot.pack(fill="both", expand=False, padx=10, pady=(0, 10))

        ttk.Label(bot, text="Selected event (JSON):", style="Panel.TLabel").pack(
            anchor="w", pady=(0, 4)
        )

        self.json_text = tk.Text(
            bot,
            height=10,
            bg=C["panel"],
            fg=C["text"],
            insertbackground=C["text"],
            relief="flat",
            wrap="none",
        )
        self.json_text.pack(fill="both", expand=True)

    def _selected_impacts(self) -> List[str]:
        impacts: List[str] = []
        if self.impact_high.get():
            impacts.append("High")
        if self.impact_med.get():
            impacts.append("Medium")
        if self.impact_low.get():
            impacts.append("Low")
        return impacts

    def refresh_async(self) -> None:
        if self._refresh_inflight:
            return
        self._refresh_inflight = True

        self.refresh_btn.configure(state="disabled")
        self.status.configure(text="Fetching calendar…")

        def worker() -> None:
            try:
                days_back = _safe_int(self.days_back_var.get(), 1)
                days_ahead = _safe_int(self.days_ahead_var.get(), 7)
                impacts = self._selected_impacts()
                currency = self.currency_var.get().strip().upper()
                currency_filter = None if currency == "ALL" else [currency]

                result = run_pipeline(
                    sources=["inv"],
                    impact_filter=impacts if impacts else None,
                    currency_filter=currency_filter,
                    days_back=days_back,
                    days_ahead=days_ahead,
                    export_fmt="json",
                )
                events = [_event_to_dict(e) for e in (result.events or [])]
                self.after(0, lambda: self._apply_events(events))
            except Exception as exc:
                self.after(
                    0, lambda: self._on_error(f"Calendar refresh failed:\n{exc}")
                )
            finally:
                self.after(0, self._refresh_done)

        threading.Thread(target=worker, daemon=True).start()

    def _refresh_done(self) -> None:
        self._refresh_inflight = False
        self.refresh_btn.configure(state="normal")

    def _apply_events(self, events: List[Dict[str, Any]]) -> None:
        self._events = events
        _treeview_clear(self.tv)

        for i, e in enumerate(events):
            self.tv.insert(
                "",
                "end",
                iid=str(i),
                values=(
                    e.get("date", ""),
                    e.get("time", ""),
                    e.get("currency", ""),
                    e.get("impact", ""),
                    e.get("title", ""),
                    e.get("source", ""),
                    e.get("actual", ""),
                    e.get("forecast", ""),
                    e.get("previous", ""),
                ),
            )

        self.status.configure(
            text=f"Loaded {len(events)} events. Pipeline JSON saved in `scrape/output/`."
        )

    def _on_error(self, msg: str) -> None:
        messagebox.showerror("Error", msg)
        self.status.configure(text="Error.")

    def _on_select_event(self, _evt: Any) -> None:
        sel = self.tv.selection()
        if not sel:
            return
        try:
            idx = int(sel[0])
        except Exception:
            return
        if idx < 0 or idx >= len(self._events):
            return
        obj = self._events[idx]
        self.json_text.delete("1.0", "end")
        self.json_text.insert("1.0", _pretty_json(obj))

    def export_json(self) -> None:
        if not self._events:
            messagebox.showinfo(
                "Export", "No events loaded yet. Click Refresh Calendar first."
            )
            return
        path = filedialog.asksaveasfilename(
            title="Export calendar JSON",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile="economic_calendar_ui_export.json",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._events, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("Export", f"Saved:\n{path}")
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))


# ============================================================
# Prices Tab
# ============================================================


class PricesTab(ttk.Frame):
    def __init__(self, parent: ttk.Notebook):
        super().__init__(parent)
        self.configure(style="Panel.TFrame")

        self.scraper = YahooFinancePriceScraper(output_dir=None)

        self._history_rows: List[Dict[str, Any]] = []
        self._quote_row: Optional[Dict[str, Any]] = None
        self._refresh_inflight = False

        self._build_controls()
        self._build_chart_and_table()
        self._build_json_view()

    # ----------------------------
    # Guardrails for Yahoo limits
    # ----------------------------
    def _normalize_interval_period(
        self, interval: str, period: str
    ) -> Tuple[str, str, Optional[str]]:
        """
        Yahoo Finance limitations (common):
        - 1m interval cannot be fetched for long periods (often max ~7-8 days).
        - Smaller intervals (5m/15m/30m) also have limited lookbacks.

        We enforce a safe combination to avoid "no price data found" / misleading delisted errors.

        Returns: (interval, period, note_to_user)
        """
        interval = (interval or "").strip()
        period = (period or "").strip()

        # Safe defaults
        if not interval:
            interval = "1d"
        if not period:
            period = "1mo"

        note: Optional[str] = None

        # Hard guard for 1m
        if interval == "1m" and period not in ("1d", "5d"):
            note = (
                "Interval 1m hanya bisa ± sampai 8 hari. Period otomatis di-set ke 5d."
            )
            period = "5d"

        # Soft guards for other intraday intervals (keep it simple)
        if interval in ("5m", "15m", "30m") and period in (
            "2y",
            "5y",
            "10y",
            "max",
            "ytd",
        ):
            note = f"Interval {interval} tidak cocok untuk period {period}. Period otomatis di-set ke 1mo."
            period = "1mo"

        # If user chooses 1h, keep period reasonable (still allow large, but reduce worst-cases)
        if interval == "1h" and period in ("10y", "max"):
            note = f"Interval {interval} untuk {period} sering gagal di Yahoo. Period otomatis di-set ke 2y."
            period = "2y"

        return interval, period, note

    def _is_yfinance_rate_limit_error(self, exc: Exception) -> bool:
        msg = str(exc).lower()
        return (
            ("too many requests" in msg)
            or ("rate limit" in msg)
            or ("ratelimited" in msg)
        )

    def _is_yahoo_granularity_window_error(self, exc: Exception) -> bool:
        msg = str(exc).lower()
        return ("only" in msg and "days worth of 1m granularity data" in msg) or (
            "1m data not available" in msg
        )

    def _is_yahoo_no_price_data(self, exc: Exception) -> bool:
        msg = str(exc).lower()
        return ("possibly delisted" in msg) or ("no price data found" in msg)

    def _build_controls(self) -> None:
        top = ttk.Frame(self, style="Panel.TFrame")
        top.pack(fill="x", padx=10, pady=10)

        ttk.Label(top, text="Instrument:", style="Panel.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.instrument_var = tk.StringVar(value="USDIDR")
        inst = ttk.Combobox(
            top, textvariable=self.instrument_var, state="readonly", width=10
        )
        inst["values"] = ("USDIDR", "IHSG", "BBCA")
        inst.grid(row=0, column=1, padx=(6, 14), sticky="w")

        ttk.Label(top, text="Interval:", style="Panel.TLabel").grid(
            row=0, column=2, sticky="w"
        )
        self.interval_var = tk.StringVar(value="1d")
        interval = ttk.Combobox(
            top, textvariable=self.interval_var, state="readonly", width=8
        )
        interval["values"] = (
            "1m",
            "5m",
            "15m",
            "30m",
            "1h",
            "1d",
            "5d",
            "1wk",
            "1mo",
            "3mo",
        )
        interval.grid(row=0, column=3, padx=(6, 14), sticky="w")

        # If user changes interval, we can auto-correct period later in refresh.

        ttk.Label(top, text="Period:", style="Panel.TLabel").grid(
            row=0, column=4, sticky="w"
        )
        self.period_var = tk.StringVar(value="3mo")
        period = ttk.Combobox(
            top, textvariable=self.period_var, state="readonly", width=10
        )
        period["values"] = (
            "5d",
            "1mo",
            "3mo",
            "6mo",
            "1y",
            "2y",
            "5y",
            "10y",
            "ytd",
            "max",
        )
        period.grid(row=0, column=5, padx=(6, 14), sticky="w")

        self.auto_adjust = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="Auto-adjust", variable=self.auto_adjust).grid(
            row=1, column=0, sticky="w", pady=(8, 0)
        )

        btns = ttk.Frame(top, style="Panel.TFrame")
        btns.grid(row=0, column=6, rowspan=2, sticky="e", padx=(20, 0))

        self.refresh_btn = ttk.Button(
            btns, text="Refresh Prices", command=self.refresh_async
        )
        self.refresh_btn.pack(fill="x", pady=(0, 6))

        self.export_btn = ttk.Button(
            btns, text="Export JSON…", command=self.export_json
        )
        self.export_btn.pack(fill="x")

        self.status = ttk.Label(top, text="Ready.", style="Sub.TLabel")
        self.status.grid(row=2, column=0, columnspan=7, sticky="w", pady=(10, 0))

        top.columnconfigure(6, weight=1)

    def _build_chart_and_table(self) -> None:
        wrap = ttk.Frame(self, style="Panel.TFrame")
        wrap.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        wrap.columnconfigure(0, weight=3)
        wrap.columnconfigure(1, weight=2)
        wrap.rowconfigure(0, weight=1)

        # Chart (pure Tk Canvas)
        chart_frame = ttk.Frame(wrap, style="Panel.TFrame")
        chart_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self.chart = CanvasLineChart(chart_frame, height=420)
        self.chart.pack(fill="both", expand=True)

        # Table
        table_frame = ttk.Frame(wrap, style="Panel.TFrame")
        table_frame.grid(row=0, column=1, sticky="nsew")

        cols = ("datetime_utc", "open", "high", "low", "close", "volume")
        self.tv = ttk.Treeview(table_frame, columns=cols, show="headings", height=14)

        headings = {
            "datetime_utc": "Datetime (UTC)",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Vol",
        }
        widths = {
            "datetime_utc": 160,
            "open": 70,
            "high": 70,
            "low": 70,
            "close": 70,
            "volume": 80,
        }

        for c in cols:
            self.tv.heading(c, text=headings[c])
            self.tv.column(c, width=widths[c], anchor="w")

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tv.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tv.xview)
        self.tv.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tv.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

    def _build_json_view(self) -> None:
        bot = ttk.Frame(self, style="Panel.TFrame")
        bot.pack(fill="both", expand=False, padx=10, pady=(0, 10))

        ttk.Label(bot, text="Quote snapshot (JSON):", style="Panel.TLabel").pack(
            anchor="w", pady=(0, 4)
        )
        self.quote_text = tk.Text(
            bot,
            height=8,
            bg=C["panel"],
            fg=C["text"],
            insertbackground=C["text"],
            relief="flat",
            wrap="none",
        )
        self.quote_text.pack(fill="both", expand=True)

    def _symbol_for_instrument(self, inst: str) -> Tuple[str, str]:
        inst = (inst or "").strip().upper()
        if inst == "USDIDR":
            return "USDIDR", "IDR=X"
        if inst == "IHSG":
            return "IHSG", "^JKSE"
        if inst == "BBCA":
            return "BBCA", "BBCA.JK"
        return inst, inst

    def refresh_async(self) -> None:
        if self._refresh_inflight:
            return
        self._refresh_inflight = True

        self.refresh_btn.configure(state="disabled")
        self.status.configure(text="Fetching prices…")

        def worker() -> None:
            try:
                label, symbol = self._symbol_for_instrument(self.instrument_var.get())

                raw_interval = self.interval_var.get().strip()
                raw_period = self.period_var.get().strip()
                interval, period, note = self._normalize_interval_period(
                    raw_interval, raw_period
                )

                # If we adjusted the user's selection, reflect it in UI (thread-safe via after)
                if interval != raw_interval or period != raw_period:
                    self.after(0, lambda: self.interval_var.set(interval))
                    self.after(0, lambda: self.period_var.set(period))

                if note:
                    self.after(0, lambda: self.status.configure(text=note))

                quote: QuoteSnapshot = self.scraper.fetch_quote(
                    symbol=symbol, ticker_label=label
                )

                bars = self.scraper.fetch_history(
                    symbol=symbol,
                    ticker_label=label,
                    interval=interval,
                    period=period,
                    start=None,
                    end=None,
                    auto_adjust=bool(self.auto_adjust.get()),
                )

                quote_row = asdict(quote)
                history_rows = [asdict(b) for b in bars]

                # Handle "empty history" as user-friendly message (often rate limit or Yahoo restriction)
                if not history_rows:
                    # Still show quote JSON, but tell user about common causes.
                    msg = (
                        "History kosong dari Yahoo.\n\n"
                        "Penyebab umum:\n"
                        "- Rate limit (Too Many Requests)\n"
                        "- Kombinasi interval/period tidak didukung\n\n"
                        "Coba:\n"
                        "- ganti interval ke 1d\n"
                        "- pilih period 5d / 1mo\n"
                        "- tunggu beberapa menit lalu refresh"
                    )
                    self.after(0, lambda: self.quote_text.delete("1.0", "end"))
                    self.after(
                        0,
                        lambda: self.quote_text.insert("1.0", _pretty_json(quote_row)),
                    )
                    self.after(
                        0,
                        lambda: self.status.configure(
                            text="History kosong (lihat quote JSON)."
                        ),
                    )
                    self.after(0, lambda: messagebox.showwarning("Yahoo Finance", msg))
                    return

                self.after(
                    0,
                    lambda: self._apply_prices(label, symbol, quote_row, history_rows),
                )
            except Exception as exc:
                # Friendly messages for common failures
                if self._is_yfinance_rate_limit_error(exc):
                    msg = (
                        "Yahoo Finance rate limit (Too Many Requests).\n\n"
                        "Tunggu 10–30 menit, jangan spam refresh, lalu coba lagi."
                    )
                    self.after(0, lambda: messagebox.showwarning("Rate limit", msg))
                    self.after(
                        0,
                        lambda: self.status.configure(
                            text="Rate limited by Yahoo. Try later."
                        ),
                    )
                elif self._is_yahoo_granularity_window_error(exc):
                    msg = (
                        "Batas Yahoo untuk interval 1m tercapai.\n\n"
                        "Solusi:\n"
                        "- pakai interval 1d untuk period panjang\n"
                        "- atau interval 1m hanya untuk period 5d"
                    )
                    self.after(0, lambda: messagebox.showwarning("Interval limit", msg))
                    self.after(
                        0,
                        lambda: self.status.configure(
                            text="Interval/period not supported. Adjusted."
                        ),
                    )
                elif self._is_yahoo_no_price_data(exc):
                    msg = (
                        "Yahoo mengembalikan 'no price data found / possibly delisted'.\n\n"
                        "Biasanya ini bukan delisted, tapi:\n"
                        "- rate limit\n"
                        "- interval/period tidak didukung\n\n"
                        "Coba interval=1d dan period=1mo, lalu refresh."
                    )
                    self.after(0, lambda: messagebox.showwarning("No data", msg))
                    self.after(
                        0,
                        lambda: self.status.configure(
                            text="Yahoo returned no price data."
                        ),
                    )
                else:
                    self.after(
                        0, lambda: self._on_error(f"Price refresh failed:\n{exc}")
                    )
            finally:
                self.after(0, self._refresh_done)

        threading.Thread(target=worker, daemon=True).start()

    def _refresh_done(self) -> None:
        self._refresh_inflight = False
        self.refresh_btn.configure(state="normal")

    def _apply_prices(
        self,
        label: str,
        symbol: str,
        quote_row: Dict[str, Any],
        history_rows: List[Dict[str, Any]],
    ) -> None:
        self._quote_row = quote_row
        self._history_rows = history_rows

        # Quote JSON view
        self.quote_text.delete("1.0", "end")
        self.quote_text.insert("1.0", _pretty_json(quote_row))

        # Table: show last N bars
        _treeview_clear(self.tv)
        show_rows = history_rows[-200:] if len(history_rows) > 200 else history_rows
        for i, r in enumerate(show_rows):
            self.tv.insert(
                "",
                "end",
                iid=str(i),
                values=(
                    r.get("datetime_utc", ""),
                    r.get("open", ""),
                    r.get("high", ""),
                    r.get("low", ""),
                    r.get("close", ""),
                    r.get("volume", ""),
                ),
            )

        # Chart points (close)
        pts: List[Tuple[datetime, float]] = []
        for r in history_rows:
            dt_s = r.get("datetime_utc")
            close_v = r.get("close")
            if not dt_s or close_v is None:
                continue
            try:
                dt = datetime.fromisoformat(
                    str(dt_s).replace("Z", "+00:00")
                ).astimezone(timezone.utc)
                pts.append((dt, float(close_v)))
            except Exception:
                continue

        self.chart.set_title(f"{label} ({symbol})", subtitle="Close price (UTC)")
        self.chart.set_y_label("Close")
        self.chart.set_series(pts)

        self.status.configure(
            text=f"Loaded {len(history_rows)} history bars. Quote at {quote_row.get('fetched_at_utc')}"
        )

    def _on_error(self, msg: str) -> None:
        messagebox.showerror("Error", msg)
        self.status.configure(text="Error.")

    def export_json(self) -> None:
        if not self._quote_row and not self._history_rows:
            messagebox.showinfo(
                "Export", "No data loaded yet. Click Refresh Prices first."
            )
            return
        payload = {
            "exported_at_utc": _utc_now_rfc3339(),
            "quote": self._quote_row,
            "history": self._history_rows,
        }
        path = filedialog.asksaveasfilename(
            title="Export prices JSON",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile="prices_ui_export.json",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("Export", f"Saved:\n{path}")
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))


# ============================================================
# App Shell
# ============================================================


class PBLDesktopApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("PBL Dashboard - Economic Calendar & Prices")
        self.configure(bg=C["bg"])
        self.geometry("1200x780")
        self.minsize(1100, 720)

        self._apply_ttk_theme()

        header = ttk.Frame(self, style="Panel.TFrame")
        header.pack(fill="x", padx=12, pady=(12, 6))

        ttk.Label(header, text="PBL Desktop App", style="Title.TLabel").pack(
            side="left"
        )

        self.clock = ttk.Label(header, text="", style="Sub.TLabel")
        self.clock.pack(side="right")
        self._tick_clock()

        nb = ttk.Notebook(self, style="Dark.TNotebook")
        nb.pack(fill="both", expand=True, padx=12, pady=12)

        cal = CalendarTab(nb)
        prices = PricesTab(nb)

        nb.add(cal, text=" Economic Calendar ")
        nb.add(prices, text=" Prices ")

        footer = ttk.Frame(self, style="Panel.TFrame")
        footer.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Label(
            footer,
            text="Tip: Calendar refresh also writes JSON to `scrape/output/` (pipeline).",
            style="Sub.TLabel",
        ).pack(side="left")

    def _tick_clock(self) -> None:
        self.clock.configure(text=f"UTC: {_utc_now_rfc3339()}")
        self.after(1000, self._tick_clock)

    def _apply_ttk_theme(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("Panel.TFrame", background=C["bg"])
        style.configure(
            "Panel.TLabel",
            background=C["bg"],
            foreground=C["text"],
            font=("Consolas", 10),
        )
        style.configure(
            "Sub.TLabel",
            background=C["bg"],
            foreground=C["subtext"],
            font=("Consolas", 9),
        )
        style.configure(
            "Title.TLabel",
            background=C["bg"],
            foreground=C["text"],
            font=("Consolas", 14, "bold"),
        )

        style.configure("TCheckbutton", background=C["bg"], foreground=C["text"])
        style.map(
            "TCheckbutton",
            background=[("active", C["bg"])],
            foreground=[("active", C["text"])],
        )

        style.configure("TEntry", fieldbackground=C["panel"], foreground=C["text"])
        style.configure("TCombobox", fieldbackground=C["panel"], foreground=C["text"])
        style.map("TCombobox", fieldbackground=[("readonly", C["panel"])])

        style.configure("TButton", padding=6)
        style.configure("Dark.TNotebook", background=C["bg"], borderwidth=0)
        style.configure(
            "Dark.TNotebook.Tab",
            background=C["surface"],
            foreground=C["subtext"],
            padding=[12, 6],
            font=("Consolas", 10),
        )
        style.map(
            "Dark.TNotebook.Tab",
            background=[("selected", C["surface2"])],
            foreground=[("selected", C["text"])],
        )


def main() -> None:
    app = PBLDesktopApp()
    app.mainloop()


if __name__ == "__main__":
    main()
