# ============================================================
# Yahoo Finance Price Scraper (no pandas in YOUR code)
# ============================================================
#
# Goal
# ----
# Fetch:
# - Quote snapshot (best-effort)
# - Historical OHLCV bars
#
# Without adding pandas as an explicit dependency in this repo.
#
# Important reality check
# -----------------------
# `yfinance` itself commonly depends on `pandas` internally.
# This file avoids importing pandas directly, but if your environment
# does not have pandas, `yfinance` may still fail at runtime depending
# on its version and code paths.
#
# If that happens, the real fix is either:
# - install pandas (not desired in your case), OR
# - bypass yfinance and hit a lightweight HTTP endpoint directly.
#
# This implementation:
# - Uses `yfinance.download()` so you can fetch history in one call.
# - Normalizes the result into plain Python dict/dataclasses using
#   safe, best-effort conversions.
#
# Targets (default)
# -----------------
# - USD/IDR FX:      "IDR=X"
# - IHSG index:      "^JKSE"
# - BBCA stock:      "BBCA.JK"
#
# Usage
# -----
# python scrapers/yfinance_price_scraper.py
# python scrapers/yfinance_price_scraper.py --tickers IDR=X ^JKSE BBCA.JK
# python scrapers/yfinance_price_scraper.py --labels USDIDR IHSG BBCA
# python scrapers/yfinance_price_scraper.py --period 6mo --interval 1d
# python scrapers/yfinance_price_scraper.py --start 2024-01-01 --end 2024-12-31
# python scrapers/yfinance_price_scraper.py --fmt json
# python scrapers/yfinance_price_scraper.py --no-export
#
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

# Allow running directly: `python scrapers/yfinance_price_scraper.py`
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    import config  # type: ignore
except Exception:
    config = None  # fallback for standalone usage outside this repo

try:
    import yfinance as yf  # type: ignore
except Exception as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency: yfinance. Install with `pip install yfinance`."
    ) from exc


DEFAULT_TICKERS: Dict[str, str] = {
    "USDIDR": "IDR=X",
    "IHSG": "^JKSE",
    "BBCA": "BBCA.JK",
}


@dataclass(frozen=True)
class PriceBar:
    """
    Normalized OHLCV record.

    `datetime_utc` is RFC3339 (UTC, Z-suffix).
    """

    ticker: str
    symbol: str
    interval: str

    datetime_utc: str
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: Optional[float]
    adj_close: Optional[float]
    volume: Optional[float]


@dataclass(frozen=True)
class QuoteSnapshot:
    """
    Best-effort quote snapshot from yfinance.Ticker(...).fast_info/.info.

    Fields are optional because Yahoo often omits some for certain instruments.
    """

    ticker: str
    symbol: str
    fetched_at_utc: str

    currency: Optional[str]
    exchange: Optional[str]
    quote_type: Optional[str]

    last_price: Optional[float]
    previous_close: Optional[float]
    open: Optional[float]
    day_high: Optional[float]
    day_low: Optional[float]

    change: Optional[float]
    change_percent: Optional[float]

    market_time_utc: Optional[str]


def _utc_now_rfc3339() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
        if f != f:  # NaN
            return None
        return f
    except Exception:
        return None


def _safe_get(d: Any, *keys: str) -> Any:
    if not isinstance(d, dict):
        # yfinance fast_info sometimes isn't a plain dict, but it behaves like one.
        try:
            d = dict(d)
        except Exception:
            return None
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def _epoch_to_rfc3339_utc(v: Any) -> Optional[str]:
    try:
        if v is None:
            return None
        dt = datetime.fromtimestamp(int(v), tz=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    except Exception:
        return None


def _dt_like_to_rfc3339_utc(v: Any) -> Optional[str]:
    """
    Attempt to convert various datetime-like values to RFC3339 in UTC.

    Handles:
    - datetime (naive => assume UTC)
    - objects with `to_pydatetime()`
    - string ISO-like values (best effort)
    """
    if v is None:
        return None

    if isinstance(v, datetime):
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        else:
            v = v.astimezone(timezone.utc)
        return v.isoformat().replace("+00:00", "Z")

    # pandas Timestamp has .to_pydatetime(); we don't import pandas but can support it.
    to_py = getattr(v, "to_pydatetime", None)
    if callable(to_py):
        try:
            return _dt_like_to_rfc3339_utc(to_py())
        except Exception:
            return None

    # If it's already a string, try to parse lightly.
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            # Support trailing Z
            s2 = s.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s2)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            return dt.isoformat().replace("+00:00", "Z")
        except Exception:
            return None

    return None


def _ensure_output_dir(output_dir: str) -> None:
    os.makedirs(output_dir, exist_ok=True)


def _write_json(path: str, payload: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _write_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("")
        return

    fieldnames: List[str] = list(rows[0].keys())
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _iter_history_rows(history_obj: Any) -> Iterable[Tuple[Any, Dict[str, Any]]]:
    """
    Iterate rows from yfinance history/download output without hard dependency on pandas.

    We try multiple strategies:
    1) DataFrame-like: `.iterrows()` yields (index, rowSeries)
    2) Dict-like: {datetime->rowdict} (rare)
    """
    if history_obj is None:
        return []

    # DataFrame-like
    it = getattr(history_obj, "iterrows", None)
    if callable(it):

        def gen() -> Iterable[Tuple[Any, Dict[str, Any]]]:
            for idx, row in it():
                # row could be Series-like; convert to dict best-effort
                if isinstance(row, dict):
                    yield idx, row
                else:
                    to_dict = getattr(row, "to_dict", None)
                    if callable(to_dict):
                        try:
                            yield idx, dict(to_dict())
                            continue
                        except Exception:
                            pass
                    # fallback: try dict(row)
                    try:
                        yield idx, dict(row)
                    except Exception:
                        # worst-case: nothing usable
                        yield idx, {}

        return gen()

    # Dict-like
    if isinstance(history_obj, dict):

        def gen2() -> Iterable[Tuple[Any, Dict[str, Any]]]:
            for k, v in history_obj.items():
                yield k, v if isinstance(v, dict) else {}

        return gen2()

    return []


class YahooFinancePriceScraper:
    def __init__(self, output_dir: Optional[str] = None) -> None:
        if output_dir:
            self.output_dir = output_dir
        else:
            self.output_dir = (
                getattr(config, "OUTPUT_DIR", "output") if config else "output"
            )

    def fetch_quote(self, symbol: str, ticker_label: str) -> QuoteSnapshot:
        """
        Fetch a best-effort current quote snapshot.

        Tries:
        - `fast_info` (lighter, sometimes more reliable)
        - `.info` (heavier; can be slow / rate-limited)
        """
        fetched_at = _utc_now_rfc3339()
        t = yf.Ticker(symbol)

        out: Dict[str, Any] = {
            "ticker": ticker_label,
            "symbol": symbol,
            "fetched_at_utc": fetched_at,
            "currency": None,
            "exchange": None,
            "quote_type": None,
            "last_price": None,
            "previous_close": None,
            "open": None,
            "day_high": None,
            "day_low": None,
            "change": None,
            "change_percent": None,
            "market_time_utc": None,
        }

        # 1) fast_info (dict-like)
        try:
            fi = getattr(t, "fast_info", None)
            if fi:
                # Convert to dict-like safely
                try:
                    fi_dict = dict(fi)
                except Exception:
                    fi_dict = fi if isinstance(fi, dict) else {}

                out["currency"] = _safe_get(fi_dict, "currency") or out["currency"]
                out["exchange"] = _safe_get(fi_dict, "exchange") or out["exchange"]

                last = _safe_get(
                    fi_dict,
                    "last_price",
                    "lastPrice",
                    "regular_market_price",
                    "regularMarketPrice",
                )
                prev = _safe_get(
                    fi_dict,
                    "previous_close",
                    "previousClose",
                    "regular_market_previous_close",
                    "regularMarketPreviousClose",
                )
                opn = _safe_get(
                    fi_dict,
                    "open",
                    "regular_market_open",
                    "regularMarketOpen",
                )
                hi = _safe_get(
                    fi_dict,
                    "day_high",
                    "dayHigh",
                    "regular_market_day_high",
                    "regularMarketDayHigh",
                )
                lo = _safe_get(
                    fi_dict,
                    "day_low",
                    "dayLow",
                    "regular_market_day_low",
                    "regularMarketDayLow",
                )

                out["last_price"] = _to_float(last)
                out["previous_close"] = _to_float(prev)
                out["open"] = _to_float(opn)
                out["day_high"] = _to_float(hi)
                out["day_low"] = _to_float(lo)

                mt = _safe_get(
                    fi_dict,
                    "last_market_time",
                    "lastMarketTime",
                    "regular_market_time",
                    "regularMarketTime",
                )
                out["market_time_utc"] = (
                    _epoch_to_rfc3339_utc(mt) or out["market_time_utc"]
                )
        except Exception:
            pass

        # 2) info fallback
        try:
            info = getattr(t, "info", None) or {}
            if isinstance(info, dict) and info:
                out["currency"] = _safe_get(info, "currency") or out["currency"]
                out["exchange"] = _safe_get(info, "exchange") or out["exchange"]
                out["quote_type"] = _safe_get(info, "quoteType") or out["quote_type"]

                if out["last_price"] is None:
                    out["last_price"] = _to_float(
                        _safe_get(info, "regularMarketPrice", "currentPrice")
                    )
                if out["previous_close"] is None:
                    out["previous_close"] = _to_float(
                        _safe_get(info, "regularMarketPreviousClose", "previousClose")
                    )
                if out["open"] is None:
                    out["open"] = _to_float(
                        _safe_get(info, "regularMarketOpen", "open")
                    )
                if out["day_high"] is None:
                    out["day_high"] = _to_float(
                        _safe_get(info, "regularMarketDayHigh", "dayHigh")
                    )
                if out["day_low"] is None:
                    out["day_low"] = _to_float(
                        _safe_get(info, "regularMarketDayLow", "dayLow")
                    )

                if out["market_time_utc"] is None:
                    out["market_time_utc"] = _epoch_to_rfc3339_utc(
                        _safe_get(info, "regularMarketTime")
                    )
        except Exception:
            pass

        # compute change / change%
        last_p = out["last_price"]
        prev_c = out["previous_close"]
        if (
            isinstance(last_p, (int, float))
            and isinstance(prev_c, (int, float))
            and prev_c != 0
        ):
            out["change"] = float(last_p) - float(prev_c)
            out["change_percent"] = (float(out["change"]) / float(prev_c)) * 100.0

        return QuoteSnapshot(**out)

    def fetch_history(
        self,
        symbol: str,
        ticker_label: str,
        interval: str = "1d",
        period: Optional[str] = "3mo",
        start: Optional[str] = None,
        end: Optional[str] = None,
        auto_adjust: bool = False,
    ) -> List[PriceBar]:
        """
        Fetch historical OHLCV bars via `yfinance.download()` (best-effort).

        You can specify either:
        - `period` (e.g. '3mo') OR
        - `start` / `end` (YYYY-MM-DD strings)

        Returns a list of PriceBar with RFC3339 UTC timestamps.
        """
        # yfinance.download can fetch quickly; group_by='column' gives normal columns.
        # If multiple tickers are passed, it returns multiindex columns; we only pass one.
        data = yf.download(
            tickers=symbol,
            interval=interval,
            period=None if start else period,
            start=start,
            end=end,
            auto_adjust=auto_adjust,
            progress=False,
            group_by="column",
            threads=False,
        )

        bars: List[PriceBar] = []
        for idx, row in _iter_history_rows(data):
            dt_utc = _dt_like_to_rfc3339_utc(idx)
            if not dt_utc:
                continue

            # Column keys can be 'Open'/'High' etc. Use a few variations.
            def get_col(*names: str) -> Any:
                for n in names:
                    if isinstance(row, dict) and n in row:
                        return row.get(n)
                return None

            o = _to_float(get_col("Open", "open"))
            h = _to_float(get_col("High", "high"))
            l = _to_float(get_col("Low", "low"))
            c = _to_float(get_col("Close", "close"))
            ac = _to_float(get_col("Adj Close", "AdjClose", "adj_close", "adjclose"))
            v = _to_float(get_col("Volume", "volume"))

            bars.append(
                PriceBar(
                    ticker=ticker_label,
                    symbol=symbol,
                    interval=interval,
                    datetime_utc=dt_utc,
                    open=o,
                    high=h,
                    low=l,
                    close=c,
                    adj_close=ac,
                    volume=v,
                )
            )

        return bars

    def export(
        self,
        quotes: List[QuoteSnapshot],
        bars: List[PriceBar],
        fmt: str = "both",  # json|csv|both
        filename_prefix: str = "yfinance_prices",
    ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        """
        Export quote snapshots and historical bars into output_dir.

        Returns paths:
        - quotes_json_path, quotes_csv_path, bars_json_path, bars_csv_path
        """
        _ensure_output_dir(self.output_dir)

        fmt = (fmt or "both").lower().strip()
        export_json = fmt in ("json", "both")
        export_csv = fmt in ("csv", "both")

        quotes_rows = [asdict(q) for q in quotes]
        bars_rows = [asdict(b) for b in bars]

        quotes_json_path = os.path.join(
            self.output_dir, f"{filename_prefix}_quotes.json"
        )
        quotes_csv_path = os.path.join(self.output_dir, f"{filename_prefix}_quotes.csv")
        bars_json_path = os.path.join(
            self.output_dir, f"{filename_prefix}_history.json"
        )
        bars_csv_path = os.path.join(self.output_dir, f"{filename_prefix}_history.csv")

        if export_json:
            _write_json(quotes_json_path, quotes_rows)
            _write_json(bars_json_path, bars_rows)
        else:
            quotes_json_path = None
            bars_json_path = None

        if export_csv:
            _write_csv(quotes_csv_path, quotes_rows)
            _write_csv(bars_csv_path, bars_rows)
        else:
            quotes_csv_path = None
            bars_csv_path = None

        return quotes_json_path, quotes_csv_path, bars_json_path, bars_csv_path


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Yahoo Finance price scraper (yfinance)")
    p.add_argument(
        "--tickers",
        nargs="*",
        default=list(DEFAULT_TICKERS.values()),
        help="Symbols to fetch (e.g., IDR=X ^JKSE BBCA.JK). Default: USD/IDR, IHSG, BBCA",
    )
    p.add_argument(
        "--labels",
        nargs="*",
        default=list(DEFAULT_TICKERS.keys()),
        help="Optional labels aligned with --tickers (e.g., USDIDR IHSG BBCA).",
    )
    p.add_argument("--interval", default="1d", help="History interval (default: 1d)")
    p.add_argument(
        "--period",
        default="3mo",
        help="History period (default: 3mo). Ignored if --start is set.",
    )
    p.add_argument(
        "--start", default=None, help="History start date YYYY-MM-DD (optional)"
    )
    p.add_argument("--end", default=None, help="History end date YYYY-MM-DD (optional)")
    p.add_argument(
        "--auto-adjust",
        action="store_true",
        help="Use auto-adjusted prices for history (splits/dividends).",
    )
    p.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (default: config.OUTPUT_DIR or ./output)",
    )
    p.add_argument(
        "--fmt",
        default=(getattr(config, "OUTPUT_FORMAT", "both") if config else "both"),
        help="Export format: json|csv|both (default: config.OUTPUT_FORMAT or both)",
    )
    p.add_argument(
        "--no-export",
        action="store_true",
        help="Don't export files; only print summary.",
    )
    p.add_argument(
        "--prefix",
        default="yfinance_prices",
        help="Filename prefix for exports (default: yfinance_prices)",
    )
    return p


def _pair_labels_and_tickers(
    labels: List[str], tickers: List[str]
) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    for i, sym in enumerate(tickers):
        label = labels[i] if i < len(labels) else sym.replace("^", "").replace("=X", "")
        pairs.append((label, sym))
    return pairs


def main() -> None:
    args = _build_arg_parser().parse_args()

    tickers: List[str] = [t.strip() for t in (args.tickers or []) if t.strip()]
    labels: List[str] = [l.strip() for l in (args.labels or []) if l.strip()]
    pairs = _pair_labels_and_tickers(labels, tickers)

    scraper = YahooFinancePriceScraper(output_dir=args.output_dir)

    quotes: List[QuoteSnapshot] = []
    bars: List[PriceBar] = []

    for label, symbol in pairs:
        q = scraper.fetch_quote(symbol=symbol, ticker_label=label)
        quotes.append(q)

        h = scraper.fetch_history(
            symbol=symbol,
            ticker_label=label,
            interval=args.interval,
            period=args.period,
            start=args.start,
            end=args.end,
            auto_adjust=bool(args.auto_adjust),
        )
        bars.extend(h)

    print("=" * 72)
    print("Yahoo Finance Price Scraper (yfinance)")
    print(f"Fetched at (UTC): {_utc_now_rfc3339()}")
    print(f"Tickers: {', '.join([f'{lbl}:{sym}' for lbl, sym in pairs])}")
    print(
        f"History: interval={args.interval}  period={args.period}  start={args.start}  end={args.end}"
    )
    print("-" * 72)

    for q in quotes:
        lp = q.last_price
        ch = q.change
        chp = q.change_percent
        cur = q.currency or "-"
        ex = q.exchange or "-"
        mt = q.market_time_utc or "-"
        chp_disp = None if chp is None else round(chp, 4)
        print(
            f"{q.ticker:>6} ({q.symbol:<10}) "
            f"last={lp} {cur}  chg={ch} ({chp_disp}%)  "
            f"ex={ex}  mkt_time={mt}"
        )

    print("-" * 72)
    counts: Dict[str, int] = {}
    for b in bars:
        counts[b.ticker] = counts.get(b.ticker, 0) + 1
    for label, symbol in pairs:
        print(f"History bars: {label:>6} ({symbol:<10}) = {counts.get(label, 0)}")

    if args.no_export:
        print("=" * 72)
        print("Export disabled (--no-export).")
        return

    qj, qc, bj, bc = scraper.export(
        quotes=quotes,
        bars=bars,
        fmt=args.fmt,
        filename_prefix=args.prefix,
    )

    print("=" * 72)
    print("Export complete:")
    if qj:
        print(f"- quotes JSON : {qj}")
    if qc:
        print(f"- quotes CSV  : {qc}")
    if bj:
        print(f"- history JSON: {bj}")
    if bc:
        print(f"- history CSV : {bc}")


if __name__ == "__main__":
    main()
