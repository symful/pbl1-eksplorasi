from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import tkinter as tk
from dataclasses import asdict
from datetime import datetime, timedelta, timezone  # noqa: F401 (timedelta used in MarketOverviewTab)
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

# --- Import country market scraper ---
try:
    from scrape.scrapers.country_market_scraper import (  # type: ignore
        CountryMarketScraper,
        format_change,
        format_price,
        get_country_display_list,
        parse_country_code,
    )
except Exception as exc:  # pragma: no cover
    raise SystemExit(
        "Cannot import country_market_scraper. "
        "Ensure `scrape/scrapers/country_market_scraper.py` exists."
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
                impacts = self._selected_impacts()
                currency = self.currency_var.get().strip().upper()
                currency_filter = None if currency == "ALL" else [currency]

                result = run_pipeline(
                    sources=["inv"],
                    impact_filter=impacts if impacts else None,
                    currency_filter=currency_filter,
                    days_back=days_back,
                    days_ahead=0,
                    export_fmt="json",
                )
                events = [_event_to_dict(e) for e in (result.events or [])]
                self.after(0, lambda: self._apply_events(events))
            except Exception as exc:
                self.after(
                    0, lambda e=exc: self._on_error(f"Calendar refresh failed:\n{e}")
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

                # Snapshot what we will actually use (avoid late-binding surprises in lambdas).
                used_interval = interval
                used_period = period

                # If we adjusted the user's selection, reflect it in UI (thread-safe via after)
                if interval != raw_interval or period != raw_period:
                    self.after(0, lambda v=interval: self.interval_var.set(v))
                    self.after(0, lambda v=period: self.period_var.set(v))

                if note:
                    self.after(
                        0,
                        lambda t=note: self.status.configure(text=t),
                    )

                # Always show what we actually used (interval/period)
                self.after(
                    0,
                    lambda i=used_interval, p=used_period: self.status.configure(
                        text=f"Fetching prices… (interval={i}, period={p})"
                    ),
                )

                quote: QuoteSnapshot = self.scraper.fetch_quote(
                    symbol=symbol, ticker_label=label
                )

                bars = self.scraper.fetch_history(
                    symbol=symbol,
                    ticker_label=label,
                    interval=used_interval,
                    period=used_period,
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
                        "Dipakai:\n"
                        f"- interval={used_interval}\n"
                        f"- period={used_period}\n\n"
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
                        lambda i=used_interval, p=used_period: self.status.configure(
                            text=f"History kosong (interval={i}, period={p})"
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
                        0, lambda e=exc: self._on_error(f"Price refresh failed:\n{e}")
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
# Market Overview Tab  (country → index + top-5 stocks)
# ============================================================

_AUTO_REFRESH_OPTIONS: List[Tuple[str, int]] = [
    ("30 s", 30_000),
    ("1 min", 60_000),
    ("2 min", 120_000),
    ("5 min", 300_000),
]

_INTERVAL_OPTIONS = ("1m", "5m", "15m", "30m", "1h", "1d", "5d", "1wk", "1mo", "3mo")
_PERIOD_OPTIONS = (
    "1d",
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


class MarketOverviewTab(ttk.Frame):
    """
    Shows a country's benchmark index and top-5 stocks.

    Layout
    ------
    [Controls row]
    [Auto-refresh row]
    ─────────────────────────────────────────
    Chart (left 60%)  │  Quote table (right 40%)
    ─────────────────────────────────────────
    History OHLCV table
    ─────────────────────────────────────────
    JSON view (collapsible)
    """

    def __init__(self, parent: ttk.Notebook) -> None:
        super().__init__(parent)
        self.configure(style="Panel.TFrame")

        self._scraper = CountryMarketScraper()
        self._country_display = get_country_display_list()  # ["US – United States", …]

        # State
        self._instruments: List[Tuple[str, str, str]] = []  # (label, symbol, type)
        self._quotes: Dict[str, Any] = {}  # label → quote dict
        self._histories: Dict[str, List[Dict[str, Any]]] = {}  # label → bars
        self._selected_label: Optional[str] = None
        self._fetch_inflight = False
        self._quote_only_inflight = False
        self._auto_after_id: Optional[str] = None

        self._build_controls()
        self._build_main_area()
        self._build_history_table()
        self._build_json_view()

    # ------------------------------------------------------------------ #
    # Build UI                                                             #
    # ------------------------------------------------------------------ #

    def _build_controls(self) -> None:
        top = ttk.Frame(self, style="Panel.TFrame")
        top.pack(fill="x", padx=10, pady=(10, 4))

        # Row 0 – country / instrument / interval / period / buttons
        ttk.Label(top, text="Country:", style="Panel.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.country_var = tk.StringVar(value=self._country_display[0])
        country_cb = ttk.Combobox(
            top, textvariable=self.country_var, state="readonly", width=22
        )
        country_cb["values"] = self._country_display
        country_cb.grid(row=0, column=1, padx=(4, 14), sticky="w")
        country_cb.bind("<<ComboboxSelected>>", self._on_country_change)

        ttk.Label(top, text="Chart:", style="Panel.TLabel").grid(
            row=0, column=2, sticky="w"
        )
        self.chart_inst_var = tk.StringVar(value="")
        self.chart_inst_cb = ttk.Combobox(
            top, textvariable=self.chart_inst_var, state="readonly", width=16
        )
        self.chart_inst_cb.grid(row=0, column=3, padx=(4, 14), sticky="w")
        self.chart_inst_cb.bind("<<ComboboxSelected>>", self._on_chart_inst_change)

        ttk.Label(top, text="Interval:", style="Panel.TLabel").grid(
            row=0, column=4, sticky="w"
        )
        self.interval_var = tk.StringVar(value="1d")
        interval_cb = ttk.Combobox(
            top, textvariable=self.interval_var, state="readonly", width=7
        )
        interval_cb["values"] = _INTERVAL_OPTIONS
        interval_cb.grid(row=0, column=5, padx=(4, 14), sticky="w")

        ttk.Label(top, text="Period:", style="Panel.TLabel").grid(
            row=0, column=6, sticky="w"
        )
        self.period_var = tk.StringVar(value="3mo")
        period_cb = ttk.Combobox(
            top, textvariable=self.period_var, state="readonly", width=8
        )
        period_cb["values"] = _PERIOD_OPTIONS
        period_cb.grid(row=0, column=7, padx=(4, 14), sticky="w")

        btns = ttk.Frame(top, style="Panel.TFrame")
        btns.grid(row=0, column=8, rowspan=2, sticky="e", padx=(10, 0))

        self.fetch_btn = ttk.Button(
            btns, text="Fetch All", command=self._fetch_all_async
        )
        self.fetch_btn.pack(fill="x", pady=(0, 4))

        self.export_btn = ttk.Button(
            btns, text="Export JSON…", command=self._export_json
        )
        self.export_btn.pack(fill="x", pady=(0, 4))

        self.proxy_btn = ttk.Button(
            btns, text="Proxy Settings…", command=self._open_proxy_dialog
        )
        self.proxy_btn.pack(fill="x")

        top.columnconfigure(8, weight=1)

        # Row 1 – auto-refresh controls
        ar_frame = ttk.Frame(top, style="Panel.TFrame")
        ar_frame.grid(row=1, column=0, columnspan=8, sticky="w", pady=(8, 0))

        self.auto_refresh_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            ar_frame,
            text="Auto-Refresh quotes",
            variable=self.auto_refresh_var,
            command=self._on_auto_refresh_toggle,
        ).pack(side="left")

        ttk.Label(ar_frame, text="  Every:", style="Panel.TLabel").pack(side="left")
        self.ar_interval_var = tk.StringVar(value="1 min")
        ar_cb = ttk.Combobox(
            ar_frame,
            textvariable=self.ar_interval_var,
            state="readonly",
            width=8,
        )
        ar_cb["values"] = [label for label, _ in _AUTO_REFRESH_OPTIONS]
        ar_cb.pack(side="left", padx=(4, 12))
        ar_cb.bind("<<ComboboxSelected>>", self._on_ar_interval_change)

        ttk.Label(ar_frame, text="Next:", style="Sub.TLabel").pack(side="left")
        self.next_refresh_lbl = ttk.Label(
            ar_frame, text="—", style="Sub.TLabel", width=10
        )
        self.next_refresh_lbl.pack(side="left", padx=(4, 0))

        ttk.Label(
            ar_frame,
            text="  Quotes only (fast) | Full fetch updates history",
            style="Sub.TLabel",
        ).pack(side="left", padx=(12, 0))

        # Status bar
        self.status = ttk.Label(
            top, text="Select a country and click Fetch All.", style="Sub.TLabel"
        )
        self.status.grid(row=2, column=0, columnspan=9, sticky="w", pady=(8, 0))

    def _build_main_area(self) -> None:
        """Left: chart.  Right: quote summary table."""
        pane = tk.PanedWindow(
            self,
            orient="horizontal",
            bg=C["bg"],
            sashwidth=5,
            sashrelief="flat",
        )
        pane.pack(fill="both", expand=True, padx=10, pady=(4, 0))

        # ── Left: chart ──────────────────────────────────────────────
        left = ttk.Frame(pane, style="Panel.TFrame")
        pane.add(left, minsize=360, width=680)

        self.chart = CanvasLineChart(left, height=340)
        self.chart.pack(fill="both", expand=True)

        # ── Right: quote summary table ────────────────────────────────
        right = ttk.Frame(pane, style="Panel.TFrame")
        pane.add(right, minsize=260, width=420)

        ttk.Label(right, text="Market Quotes", style="Panel.TLabel").pack(
            anchor="w", padx=4, pady=(2, 2)
        )

        q_cols = ("#", "label", "symbol", "type", "last", "chg", "chg_pct", "cur")
        self.quote_tv = ttk.Treeview(
            right, columns=q_cols, show="headings", height=7, selectmode="browse"
        )
        q_headings = {
            "#": "#",
            "label": "Name",
            "symbol": "Symbol",
            "type": "Type",
            "last": "Last",
            "chg": "Change",
            "chg_pct": "Chg %",
            "cur": "Cur",
        }
        q_widths = {
            "#": 24,
            "label": 110,
            "symbol": 90,
            "type": 46,
            "last": 90,
            "chg": 80,
            "chg_pct": 72,
            "cur": 46,
        }
        for c in q_cols:
            self.quote_tv.heading(c, text=q_headings[c])
            self.quote_tv.column(c, width=q_widths[c], anchor="w", stretch=False)

        qvsb = ttk.Scrollbar(right, orient="vertical", command=self.quote_tv.yview)
        self.quote_tv.configure(yscrollcommand=qvsb.set)

        self.quote_tv.pack(side="left", fill="both", expand=True, padx=(4, 0))
        qvsb.pack(side="left", fill="y")

        self.quote_tv.bind("<<TreeviewSelect>>", self._on_quote_row_selected)
        self.quote_tv.bind("<Double-1>", self._on_quote_row_double_click)

        # Tag colours for up/down
        self.quote_tv.tag_configure("up", foreground=C["green"])
        self.quote_tv.tag_configure("dn", foreground=C["red"])
        self.quote_tv.tag_configure("idx", foreground=C["mauve"])
        self.quote_tv.tag_configure("neu", foreground=C["text"])

    def _build_history_table(self) -> None:
        hist_frame = ttk.Frame(self, style="Panel.TFrame")
        hist_frame.pack(fill="both", expand=False, padx=10, pady=(4, 0))

        ttk.Label(
            hist_frame,
            text="OHLCV History (selected instrument):",
            style="Panel.TLabel",
        ).pack(anchor="w", pady=(0, 2))

        # Inner frame uses grid so it doesn't conflict with the pack-managed label above
        inner = ttk.Frame(hist_frame, style="Panel.TFrame")
        inner.pack(fill="both", expand=True)

        h_cols = ("datetime_utc", "open", "high", "low", "close", "volume")
        self.hist_tv = ttk.Treeview(inner, columns=h_cols, show="headings", height=6)
        h_hdg = {
            "datetime_utc": "Datetime (UTC)",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }
        h_wid = {
            "datetime_utc": 170,
            "open": 90,
            "high": 90,
            "low": 90,
            "close": 90,
            "volume": 100,
        }
        for c in h_cols:
            self.hist_tv.heading(c, text=h_hdg[c])
            self.hist_tv.column(c, width=h_wid[c], anchor="w")

        hvsb = ttk.Scrollbar(inner, orient="vertical", command=self.hist_tv.yview)
        hhsb = ttk.Scrollbar(inner, orient="horizontal", command=self.hist_tv.xview)
        self.hist_tv.configure(yscrollcommand=hvsb.set, xscrollcommand=hhsb.set)

        self.hist_tv.grid(row=0, column=0, sticky="nsew")
        hvsb.grid(row=0, column=1, sticky="ns")
        hhsb.grid(row=1, column=0, sticky="ew")
        inner.rowconfigure(0, weight=1)
        inner.columnconfigure(0, weight=1)

    def _build_json_view(self) -> None:
        bot = ttk.Frame(self, style="Panel.TFrame")
        bot.pack(fill="both", expand=False, padx=10, pady=(4, 10))

        hdr = ttk.Frame(bot, style="Panel.TFrame")
        hdr.pack(fill="x")
        ttk.Label(hdr, text="Quote JSON (selected):", style="Panel.TLabel").pack(
            side="left"
        )
        self._json_visible = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            hdr,
            text="Show",
            variable=self._json_visible,
            command=self._toggle_json_view,
        ).pack(side="left", padx=(6, 0))

        self._json_container = ttk.Frame(bot, style="Panel.TFrame")
        self._json_container.pack(fill="both", expand=True)

        self.json_text = tk.Text(
            self._json_container,
            height=7,
            bg=C["panel"],
            fg=C["text"],
            insertbackground=C["text"],
            relief="flat",
            wrap="none",
        )
        self.json_text.pack(fill="both", expand=True)

    # ------------------------------------------------------------------ #
    # Event handlers                                                       #
    # ------------------------------------------------------------------ #

    def _toggle_json_view(self) -> None:
        if self._json_visible.get():
            self._json_container.pack(fill="both", expand=True)
        else:
            self._json_container.pack_forget()

    def _on_country_change(self, _evt: Any = None) -> None:
        code = parse_country_code(self.country_var.get())
        instruments = self._scraper.get_instruments(code)
        self._instruments = instruments

        labels = [label for label, _, _ in instruments]
        self.chart_inst_cb["values"] = labels
        if labels:
            self.chart_inst_var.set(labels[0])
            self._selected_label = labels[0]

        # Clear stale data
        _treeview_clear(self.quote_tv)
        _treeview_clear(self.hist_tv)
        self.chart.clear()
        self.json_text.delete("1.0", "end")
        self._quotes = {}
        self._histories = {}

        # Pre-populate quote table rows with placeholders
        for i, (label, symbol, itype) in enumerate(instruments):
            prefix = "★" if itype == "index" else " "
            self.quote_tv.insert(
                "",
                "end",
                iid=str(i),
                values=(prefix, label, symbol, itype[:3].upper(), "…", "…", "…", ""),
                tags=("idx" if itype == "index" else "neu",),
            )

        self.status.configure(
            text=f"Country changed to {code}. Click 'Fetch All' to load data."
        )

    def _on_chart_inst_change(self, _evt: Any = None) -> None:
        label = self.chart_inst_var.get()
        if label and label in self._histories:
            self._selected_label = label
            self._update_chart_and_hist_table(label)
        elif label:
            self._selected_label = label
            self._fetch_history_async(label)

    def _on_quote_row_selected(self, _evt: Any) -> None:
        sel = self.quote_tv.selection()
        if not sel:
            return
        try:
            idx = int(sel[0])
        except Exception:
            return
        if idx < 0 or idx >= len(self._instruments):
            return
        label, symbol, _ = self._instruments[idx]
        # Show JSON
        q = self._quotes.get(label)
        self.json_text.delete("1.0", "end")
        if q:
            self.json_text.insert("1.0", _pretty_json(q))

    def _on_quote_row_double_click(self, _evt: Any) -> None:
        """Double-click on quote row: fetch history for that instrument."""
        sel = self.quote_tv.selection()
        if not sel:
            return
        try:
            idx = int(sel[0])
        except Exception:
            return
        if idx < 0 or idx >= len(self._instruments):
            return
        label, symbol, _ = self._instruments[idx]
        self.chart_inst_var.set(label)
        self._selected_label = label
        if label in self._histories:
            self._update_chart_and_hist_table(label)
        else:
            self._fetch_history_async(label)

    # ------------------------------------------------------------------ #
    # Fetch logic                                                          #
    # ------------------------------------------------------------------ #

    def _get_ar_ms(self) -> int:
        """Return current auto-refresh interval in milliseconds."""
        label = self.ar_interval_var.get()
        for opt_label, opt_ms in _AUTO_REFRESH_OPTIONS:
            if opt_label == label:
                return opt_ms
        return 60_000

    def _on_auto_refresh_toggle(self) -> None:
        if self.auto_refresh_var.get():
            self._schedule_next_refresh()
        else:
            self._cancel_auto_refresh()
            self.next_refresh_lbl.configure(text="—")

    def _on_ar_interval_change(self, _evt: Any = None) -> None:
        if self.auto_refresh_var.get():
            self._cancel_auto_refresh()
            self._schedule_next_refresh()

    def _schedule_next_refresh(self) -> None:
        ms = self._get_ar_ms()
        self._auto_after_id = self.after(ms, self._auto_refresh_tick)
        # Show countdown target time
        next_dt = datetime.now(timezone.utc).replace(microsecond=0)
        next_dt = next_dt + timedelta(milliseconds=ms)
        self.next_refresh_lbl.configure(text=next_dt.strftime("%H:%M:%S"))

    def _cancel_auto_refresh(self) -> None:
        if self._auto_after_id:
            try:
                self.after_cancel(self._auto_after_id)
            except Exception:
                pass
            self._auto_after_id = None

    def _auto_refresh_tick(self) -> None:
        """Called by tkinter.after() – refreshes quotes only (fast), then reschedules."""
        if not self.auto_refresh_var.get():
            return
        if not self._instruments:
            self._schedule_next_refresh()
            return
        # Fire quote-only refresh
        self._fetch_quotes_only_async()
        self._schedule_next_refresh()

    def _fetch_all_async(self) -> None:
        """Fetch quotes + history for the currently selected instrument (full fetch)."""
        if self._fetch_inflight:
            return
        code = parse_country_code(self.country_var.get())
        if not code:
            return

        # Ensure instruments are loaded for the selected country
        if not self._instruments:
            self._on_country_change()

        self._fetch_inflight = True
        self.fetch_btn.configure(state="disabled")
        self.status.configure(text=f"Fetching all quotes for {code}…")

        interval = self.interval_var.get().strip() or "1d"
        period = self.period_var.get().strip() or "3mo"
        sel_label = self._selected_label or (
            self._instruments[0][0] if self._instruments else None
        )

        def worker() -> None:
            try:
                # 1) Concurrent quotes for all 6 instruments
                quotes_raw = self._scraper.fetch_all_quotes(code)

                # 2) History only for the currently selected instrument
                history_bars: List[Any] = []
                hist_label = sel_label
                if hist_label:
                    sym = next(
                        (s for l, s, _ in self._instruments if l == hist_label), None
                    )
                    if sym:
                        history_bars = self._scraper.fetch_history(
                            symbol=sym,
                            ticker_label=hist_label,
                            interval=interval,
                            period=period,
                        )

                # Convert to dicts
                quotes_dict = {
                    lbl: (
                        {
                            "ticker": q.ticker,
                            "symbol": q.symbol,
                            "fetched_at_utc": q.fetched_at_utc,
                            "currency": q.currency,
                            "exchange": q.exchange,
                            "quote_type": q.quote_type,
                            "last_price": q.last_price,
                            "previous_close": q.previous_close,
                            "open": q.open,
                            "day_high": q.day_high,
                            "day_low": q.day_low,
                            "change": q.change,
                            "change_percent": q.change_percent,
                            "market_time_utc": q.market_time_utc,
                        }
                        if q
                        else None
                    )
                    for lbl, q in quotes_raw.items()
                }
                history_dicts = [
                    {
                        "ticker": b.ticker,
                        "symbol": b.symbol,
                        "interval": b.interval,
                        "datetime_utc": b.datetime_utc,
                        "open": b.open,
                        "high": b.high,
                        "low": b.low,
                        "close": b.close,
                        "adj_close": b.adj_close,
                        "volume": b.volume,
                    }
                    for b in history_bars
                ]

                self.after(
                    0,
                    lambda: self._apply_full_fetch(
                        code, quotes_dict, hist_label, history_dicts, interval, period
                    ),
                )
            except Exception as exc:
                self.after(0, lambda e=exc: self._on_error(f"Fetch failed:\n{e}"))
            finally:
                self.after(0, self._fetch_done)

        threading.Thread(target=worker, daemon=True).start()

    def _fetch_done(self) -> None:
        self._fetch_inflight = False
        self.fetch_btn.configure(state="normal")

    def _fetch_quotes_only_async(self) -> None:
        """Lightweight refresh: only update current prices in the quote table."""
        if self._quote_only_inflight or self._fetch_inflight:
            return
        code = parse_country_code(self.country_var.get())
        if not code or not self._instruments:
            return

        self._quote_only_inflight = True
        self.status.configure(text=f"Auto-refreshing quotes for {code}…")

        def worker() -> None:
            try:
                quotes_raw = self._scraper.fetch_all_quotes(code)
                quotes_dict = {
                    lbl: (
                        {
                            "ticker": q.ticker,
                            "symbol": q.symbol,
                            "fetched_at_utc": q.fetched_at_utc,
                            "currency": q.currency,
                            "exchange": q.exchange,
                            "quote_type": q.quote_type,
                            "last_price": q.last_price,
                            "previous_close": q.previous_close,
                            "open": q.open,
                            "day_high": q.day_high,
                            "day_low": q.day_low,
                            "change": q.change,
                            "change_percent": q.change_percent,
                            "market_time_utc": q.market_time_utc,
                        }
                        if q
                        else None
                    )
                    for lbl, q in quotes_raw.items()
                }
                self.after(0, lambda: self._apply_quotes_update(quotes_dict))
            except Exception as exc:
                self.after(
                    0,
                    lambda e=exc: self.status.configure(
                        text=f"Auto-refresh error: {e}"
                    ),
                )
            finally:
                self.after(0, lambda: setattr(self, "_quote_only_inflight", False))

        threading.Thread(target=worker, daemon=True).start()

    def _fetch_history_async(self, label: str) -> None:
        """Fetch history for a single instrument (on demand)."""
        sym = next((s for l, s, _ in self._instruments if l == label), None)
        if not sym:
            return

        interval = self.interval_var.get().strip() or "1d"
        period = self.period_var.get().strip() or "3mo"
        self.status.configure(text=f"Fetching history for {label}…")

        def worker() -> None:
            bars = self._scraper.fetch_history(
                symbol=sym,
                ticker_label=label,
                interval=interval,
                period=period,
            )
            dicts = [
                {
                    "ticker": b.ticker,
                    "symbol": b.symbol,
                    "interval": b.interval,
                    "datetime_utc": b.datetime_utc,
                    "open": b.open,
                    "high": b.high,
                    "low": b.low,
                    "close": b.close,
                    "adj_close": b.adj_close,
                    "volume": b.volume,
                }
                for b in bars
            ]
            self.after(
                0,
                lambda: self._apply_history_update(label, sym, dicts, interval, period),
            )

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------ #
    # Apply results                                                        #
    # ------------------------------------------------------------------ #

    def _apply_full_fetch(
        self,
        code: str,
        quotes_dict: Dict[str, Any],
        hist_label: Optional[str],
        history_dicts: List[Dict[str, Any]],
        interval: str,
        period: str,
    ) -> None:
        self._quotes = quotes_dict
        if hist_label:
            self._histories[hist_label] = history_dicts

        self._update_quote_table(quotes_dict)

        if hist_label and history_dicts:
            self._update_chart_and_hist_table(hist_label)
        elif hist_label:
            self.status.configure(
                text=(
                    f"Quotes loaded ({len(quotes_dict)} instruments). "
                    f"History empty for {hist_label} "
                    f"(interval={interval}, period={period})."
                )
            )
            return

        fetched_at = _utc_now_rfc3339()
        n_ok = sum(1 for v in quotes_dict.values() if v)
        self.status.configure(
            text=(
                f"{code}: {n_ok}/{len(quotes_dict)} quotes loaded. "
                f"History for {hist_label}: {len(history_dicts)} bars. "
                f"Fetched at {fetched_at}"
            )
        )

    def _apply_quotes_update(self, quotes_dict: Dict[str, Any]) -> None:
        self._quotes = quotes_dict
        self._update_quote_table(quotes_dict)
        fetched_at = _utc_now_rfc3339()
        n_ok = sum(1 for v in quotes_dict.values() if v)
        self.status.configure(
            text=f"Quotes refreshed: {n_ok}/{len(quotes_dict)} ok. Last: {fetched_at}"
        )

    def _apply_history_update(
        self,
        label: str,
        symbol: str,
        dicts: List[Dict[str, Any]],
        interval: str,
        period: str,
    ) -> None:
        self._histories[label] = dicts
        if dicts:
            self._update_chart_and_hist_table(label)
            self.status.configure(
                text=f"History for {label} ({symbol}): {len(dicts)} bars "
                f"(interval={interval}, period={period})."
            )
        else:
            self.status.configure(
                text=(
                    f"History empty for {label}. "
                    "Check interval/period or try 1d / 3mo."
                )
            )

    def _update_quote_table(self, quotes_dict: Dict[str, Any]) -> None:
        for i, (label, symbol, itype) in enumerate(self._instruments):
            q = quotes_dict.get(label)
            if q is None:
                continue

            last_p = q.get("last_price")
            chg = q.get("change")
            chg_pct = q.get("change_percent")
            cur = q.get("currency") or ""

            last_s = format_price(last_p)
            chg_s = f"{chg:+.4g}" if chg is not None else "—"
            chg_pct_s = f"{chg_pct:+.2f}%" if chg_pct is not None else "—"

            # Colour tag
            if chg is not None and chg > 0:
                tag = "up"
            elif chg is not None and chg < 0:
                tag = "dn"
            elif itype == "index":
                tag = "idx"
            else:
                tag = "neu"

            prefix = "★" if itype == "index" else " "
            try:
                self.quote_tv.item(
                    str(i),
                    values=(
                        prefix,
                        label,
                        symbol,
                        itype[:3].upper(),
                        last_s,
                        chg_s,
                        chg_pct_s,
                        cur,
                    ),
                    tags=(tag,),
                )
            except Exception:
                pass

    def _update_chart_and_hist_table(self, label: str) -> None:
        bars = self._histories.get(label) or []

        # History table
        _treeview_clear(self.hist_tv)
        show = bars[-300:] if len(bars) > 300 else bars
        for i, r in enumerate(show):
            self.hist_tv.insert(
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

        # Chart
        pts: List[Tuple[datetime, float]] = []
        for r in bars:
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

        sym = next((s for l, s, _ in self._instruments if l == label), label)
        itype_label = next((t for l, _, t in self._instruments if l == label), "stock")
        subtitle = f"{sym}  •  Close price (UTC)"
        self.chart.set_title(
            f"{label}  ({'Index' if itype_label == 'index' else 'Stock'})",
            subtitle=subtitle,
        )
        self.chart.set_y_label("Close")
        self.chart.set_series(pts)

    # ------------------------------------------------------------------ #
    # Export / Proxy dialog                                                #
    # ------------------------------------------------------------------ #

    def _export_json(self) -> None:
        if not self._quotes:
            messagebox.showinfo("Export", "No data loaded. Click Fetch All first.")
            return
        code = parse_country_code(self.country_var.get())
        payload = {
            "exported_at_utc": _utc_now_rfc3339(),
            "country_code": code,
            "quotes": self._quotes,
            "histories": {label: bars for label, bars in self._histories.items()},
        }
        path = filedialog.asksaveasfilename(
            title="Export market snapshot JSON",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile=f"{code}_market_snapshot.json",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("Export", f"Saved:\n{path}")
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))

    def _open_proxy_dialog(self) -> None:
        """Simple dialog to set proxy URLs for the scraper."""
        dlg = tk.Toplevel(self)
        dlg.title("Proxy Settings")
        dlg.configure(bg=C["bg"])
        dlg.resizable(True, False)
        dlg.grab_set()

        ttk.Label(
            dlg,
            text=(
                "Enter proxy URLs (one per line).\n"
                "Format: http://host:port  or  http://user:pass@host:port\n"
                "Leave empty to use direct connection."
            ),
            style="Sub.TLabel",
        ).pack(padx=14, pady=(14, 6), anchor="w")

        txt = tk.Text(
            dlg,
            height=8,
            width=56,
            bg=C["panel"],
            fg=C["text"],
            insertbackground=C["text"],
            relief="flat",
        )
        txt.pack(padx=14, pady=(0, 6), fill="x")

        # Pre-populate with current proxies
        for p in self._scraper._proxies:
            txt.insert("end", p + "\n")

        status_lbl = ttk.Label(dlg, text="", style="Sub.TLabel")
        status_lbl.pack(padx=14, anchor="w")

        def _save() -> None:
            raw = txt.get("1.0", "end").strip()
            proxies = [line.strip() for line in raw.splitlines() if line.strip()]
            self._scraper.set_proxies(proxies)
            status_lbl.configure(
                text=f"Saved {len(proxies)} proxy(ies). "
                f"Workers = {self._scraper.max_workers}."
            )

        def _test() -> None:
            _save()
            status_lbl.configure(text="Testing… (check console)")

            def _do_test() -> None:
                code = parse_country_code(self.country_var.get()) or "US"
                instruments = self._scraper.get_instruments(code)
                if not instruments:
                    return
                label, symbol, _ = instruments[0]
                q = self._scraper.fetch_quote(symbol, label)
                msg = (
                    f"OK – {label}: {q.last_price} {q.currency}"
                    if q and q.last_price
                    else "No price returned (check proxy / rate limit)"
                )
                self.after(0, lambda: status_lbl.configure(text=msg))

            threading.Thread(target=_do_test, daemon=True).start()

        btns = ttk.Frame(dlg, style="Panel.TFrame")
        btns.pack(padx=14, pady=(4, 14), fill="x")
        ttk.Button(btns, text="Save", command=_save).pack(side="left", padx=(0, 6))
        ttk.Button(btns, text="Test Connection", command=_test).pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(btns, text="Close", command=dlg.destroy).pack(side="left")

        # Max-workers entry
        mw_frame = ttk.Frame(dlg, style="Panel.TFrame")
        mw_frame.pack(padx=14, pady=(0, 10), fill="x")
        ttk.Label(mw_frame, text="Concurrent workers:", style="Sub.TLabel").pack(
            side="left"
        )
        mw_var = tk.StringVar(value=str(self._scraper.max_workers))
        mw_entry = ttk.Entry(mw_frame, textvariable=mw_var, width=6)
        mw_entry.pack(side="left", padx=(6, 0))

        def _apply_mw() -> None:
            try:
                self._scraper.max_workers = max(1, int(mw_var.get()))
                status_lbl.configure(
                    text=f"Workers set to {self._scraper.max_workers}."
                )
            except Exception:
                pass

        ttk.Button(mw_frame, text="Apply", command=_apply_mw).pack(
            side="left", padx=(6, 0)
        )

    def _on_error(self, msg: str) -> None:
        messagebox.showerror("Error", msg)
        self.status.configure(text="Error — see dialog.")


# ============================================================
# Output Folder Tab  (browse output JSON / CSV files)
# ============================================================


class OutputFolderTab(ttk.Frame):
    """
    Lets the user browse all JSON / CSV files produced by the
    pipeline and the market scraper.

    Default search path: project_root/output/  and
                         desktop_app/output/  (pre-existing)
    The user can change the directory via the Browse button.
    """

    def __init__(self, parent: ttk.Notebook) -> None:
        super().__init__(parent)
        self.configure(style="Panel.TFrame")

        # Determine sensible default output dir
        _here = os.path.dirname(os.path.abspath(__file__))
        _root = os.path.abspath(os.path.join(_here, ".."))
        self._default_dirs: List[str] = [
            os.path.join(_root, "output"),
            os.path.join(_here, "output"),
        ]
        self._current_dir: str = self._default_dirs[0]
        self._file_list: List[str] = []  # full paths

        self._build_controls()
        self._build_main_pane()
        self._refresh_file_list()

    # ------------------------------------------------------------------ #
    # Build UI                                                             #
    # ------------------------------------------------------------------ #

    def _build_controls(self) -> None:
        top = ttk.Frame(self, style="Panel.TFrame")
        top.pack(fill="x", padx=10, pady=(10, 4))

        ttk.Label(top, text="Output dir:", style="Panel.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.dir_var = tk.StringVar(value=self._current_dir)
        self.dir_entry = ttk.Entry(top, textvariable=self.dir_var, width=56)
        self.dir_entry.grid(row=0, column=1, padx=(6, 6), sticky="ew")

        ttk.Button(top, text="Browse…", command=self._browse_folder).grid(
            row=0, column=2, padx=(0, 6)
        )
        ttk.Button(top, text="Refresh", command=self._refresh_file_list).grid(
            row=0, column=3, padx=(0, 6)
        )
        ttk.Button(top, text="Open Folder", command=self._open_in_explorer).grid(
            row=0, column=4, padx=(0, 6)
        )

        # Second row: quick-switch between known dirs
        qf = ttk.Frame(top, style="Panel.TFrame")
        qf.grid(row=1, column=0, columnspan=5, sticky="w", pady=(6, 0))
        ttk.Label(qf, text="Quick:", style="Sub.TLabel").pack(side="left")
        for d in self._default_dirs:
            short = os.path.basename(os.path.dirname(d)) + "/" + os.path.basename(d)
            ttk.Button(
                qf,
                text=short,
                command=lambda p=d: self._set_dir(p),
            ).pack(side="left", padx=(6, 0))

        top.columnconfigure(1, weight=1)

        self.status = ttk.Label(top, text="", style="Sub.TLabel")
        self.status.grid(row=2, column=0, columnspan=5, sticky="w", pady=(6, 0))

    def _build_main_pane(self) -> None:
        pane = tk.PanedWindow(
            self, orient="horizontal", bg=C["bg"], sashwidth=5, sashrelief="flat"
        )
        pane.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        # ── Left: file list ───────────────────────────────────────────
        left = ttk.Frame(pane, style="Panel.TFrame")
        pane.add(left, minsize=200, width=260)

        ttk.Label(left, text="Files", style="Panel.TLabel").pack(
            anchor="w", pady=(0, 2)
        )

        fl_frame = ttk.Frame(left, style="Panel.TFrame")
        fl_frame.pack(fill="both", expand=True)

        self.file_lb = tk.Listbox(
            fl_frame,
            bg=C["panel"],
            fg=C["text"],
            selectbackground=C["surface2"],
            selectforeground=C["text"],
            relief="flat",
            font=("Consolas", 9),
            activestyle="none",
        )
        fl_vsb = ttk.Scrollbar(fl_frame, orient="vertical", command=self.file_lb.yview)
        self.file_lb.configure(yscrollcommand=fl_vsb.set)

        self.file_lb.pack(side="left", fill="both", expand=True)
        fl_vsb.pack(side="left", fill="y")

        self.file_lb.bind("<<ListboxSelect>>", self._on_file_selected)

        # ── Right: content view ───────────────────────────────────────
        right = ttk.Frame(pane, style="Panel.TFrame")
        pane.add(right, minsize=400)

        ttk.Label(right, text="Contents", style="Panel.TLabel").pack(
            anchor="w", pady=(0, 2)
        )

        txt_frame = ttk.Frame(right, style="Panel.TFrame")
        txt_frame.pack(fill="both", expand=True)

        self.content_text = tk.Text(
            txt_frame,
            bg=C["panel"],
            fg=C["text"],
            insertbackground=C["text"],
            relief="flat",
            font=("Consolas", 9),
            wrap="none",
        )
        cvsb = ttk.Scrollbar(
            txt_frame, orient="vertical", command=self.content_text.yview
        )
        chsb = ttk.Scrollbar(
            txt_frame, orient="horizontal", command=self.content_text.xview
        )
        self.content_text.configure(yscrollcommand=cvsb.set, xscrollcommand=chsb.set)

        self.content_text.grid(row=0, column=0, sticky="nsew")
        cvsb.grid(row=0, column=1, sticky="ns")
        chsb.grid(row=1, column=0, sticky="ew")
        txt_frame.rowconfigure(0, weight=1)
        txt_frame.columnconfigure(0, weight=1)

        # Meta info label (file size, line count)
        self.meta_lbl = ttk.Label(right, text="", style="Sub.TLabel")
        self.meta_lbl.pack(anchor="w", pady=(4, 0))

        # Row of action buttons
        act = ttk.Frame(right, style="Panel.TFrame")
        act.pack(fill="x", pady=(4, 0))
        ttk.Button(act, text="Copy All", command=self._copy_content).pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(act, text="Save As…", command=self._save_content_as).pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(act, text="Reload File", command=self._reload_selected).pack(
            side="left"
        )

    # ------------------------------------------------------------------ #
    # File list logic                                                      #
    # ------------------------------------------------------------------ #

    def _set_dir(self, path: str) -> None:
        self.dir_var.set(path)
        self._current_dir = path
        self._refresh_file_list()

    def _refresh_file_list(self) -> None:
        self._current_dir = self.dir_var.get().strip() or self._current_dir
        self.file_lb.delete(0, "end")
        self._file_list = []
        self.content_text.delete("1.0", "end")

        if not os.path.isdir(self._current_dir):
            self.status.configure(text=f"Directory not found: {self._current_dir}")
            return

        extensions = (".json", ".csv", ".txt")
        try:
            entries = sorted(os.listdir(self._current_dir))
        except Exception as exc:
            self.status.configure(text=f"Cannot list dir: {exc}")
            return

        for name in entries:
            if any(name.lower().endswith(ext) for ext in extensions):
                full = os.path.join(self._current_dir, name)
                if os.path.isfile(full):
                    size_kb = os.path.getsize(full) / 1024
                    display = f"{name}  ({size_kb:.1f} KB)"
                    self.file_lb.insert("end", display)
                    self._file_list.append(full)

        n = len(self._file_list)
        self.status.configure(text=f"Found {n} file(s) in {self._current_dir}")

    def _on_file_selected(self, _evt: Any) -> None:
        sel = self.file_lb.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < 0 or idx >= len(self._file_list):
            return
        fpath = self._file_list[idx]
        self._load_file(fpath)

    def _reload_selected(self) -> None:
        self._on_file_selected(None)  # type: ignore[arg-type]

    def _load_file(self, fpath: str) -> None:
        self.content_text.delete("1.0", "end")
        try:
            size_bytes = os.path.getsize(fpath)
            with open(fpath, encoding="utf-8", errors="replace") as f:
                raw = f.read()

            # For JSON: pretty-print
            if fpath.lower().endswith(".json"):
                try:
                    parsed = json.loads(raw)
                    raw = json.dumps(parsed, ensure_ascii=False, indent=2)
                except Exception:
                    pass  # show raw if parse fails

            self.content_text.insert("1.0", raw)
            lines = raw.count("\n") + 1
            self.meta_lbl.configure(
                text=(
                    f"{os.path.basename(fpath)}  •  "
                    f"{size_bytes / 1024:.1f} KB  •  {lines} lines"
                )
            )
            self.status.configure(text=f"Loaded: {fpath}")
        except Exception as exc:
            self.content_text.insert("1.0", f"Error reading file:\n{exc}")
            self.status.configure(text=f"Error: {exc}")

    # ------------------------------------------------------------------ #
    # Actions                                                              #
    # ------------------------------------------------------------------ #

    def _browse_folder(self) -> None:
        chosen = filedialog.askdirectory(
            title="Select output directory",
            initialdir=self._current_dir,
        )
        if chosen:
            self._set_dir(chosen)

    def _open_in_explorer(self) -> None:
        path = self._current_dir
        if not os.path.isdir(path):
            messagebox.showwarning("Not found", f"Directory does not exist:\n{path}")
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as exc:
            messagebox.showerror("Cannot open folder", str(exc))

    def _copy_content(self) -> None:
        content = self.content_text.get("1.0", "end")
        self.clipboard_clear()
        self.clipboard_append(content)
        self.status.configure(text="Content copied to clipboard.")

    def _save_content_as(self) -> None:
        content = self.content_text.get("1.0", "end")
        if not content.strip():
            messagebox.showinfo("Save", "Nothing to save.")
            return
        path = filedialog.asksaveasfilename(
            title="Save content as…",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("CSV", "*.csv"), ("All", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self.status.configure(text=f"Saved to: {path}")
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))


# ============================================================
# App Shell
# ============================================================


class PBLDesktopApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("PBL Dashboard - Economic Calendar & Prices")
        self.configure(bg=C["bg"])
        self.geometry("1400x860")
        self.minsize(1100, 740)

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
        market = MarketOverviewTab(nb)
        output_browser = OutputFolderTab(nb)

        nb.add(cal, text=" Economic Calendar ")
        nb.add(prices, text=" Prices (Manual) ")
        nb.add(market, text=" Market Overview ")
        nb.add(output_browser, text=" Output Files ")

        footer = ttk.Frame(self, style="Panel.TFrame")
        footer.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Label(
            footer,
            text=(
                "Tip: Market Overview auto-refreshes quotes. "
                "Double-click a row to chart that instrument. "
                "Output Files tab browses all scraped JSON/CSV."
            ),
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
