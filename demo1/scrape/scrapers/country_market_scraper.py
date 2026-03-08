# ============================================================
# Country Market Scraper
# ============================================================
#
# Provides:
# - COUNTRY_TEMPLATES: pre-defined index + top-5 stocks by
#   market cap / avg daily value for 10 major markets.
# - CountryMarketScraper: wraps YahooFinancePriceScraper with
#   concurrent fetching (ThreadPoolExecutor) and round-robin
#   proxy rotation so you can distribute Yahoo Finance
#   requests across many proxy servers.
#
# Proxy usage
# -----------
# Pass a list of proxy URLs to the constructor:
#   scraper = CountryMarketScraper(
#       proxies=["http://proxy1:3128", "http://proxy2:3128"]
#   )
# Each concurrent worker picks the next proxy in round-robin
# order (thread-safe via a Lock).  If proxies=[] (default),
# requests are made directly.
#
# Yahoo Finance free-tier limits
# ------------------------------
# - Intraday 1m : max ~7-8 days lookback
# - Intraday 5m : avoid 2y+ periods
# - Rate-limit  : "Too Many Requests" → back off ~30 s
#
# The scraper returns empty lists / None on known Yahoo errors
# rather than raising, so the UI can display friendly messages.
# ============================================================

from __future__ import annotations

import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

# Allow running this file directly from the scrapers/ folder
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    import config  # type: ignore
except Exception:
    config = None

try:
    import yfinance as yf  # type: ignore
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: yfinance.  Install with `pip install yfinance`."
    ) from exc

from scrape.scrapers.yfinance_price_scraper import (  # type: ignore
    PriceBar,
    QuoteSnapshot,
    YahooFinancePriceScraper,
    _is_no_price_data_error,
    _is_rate_limit_error,
    _normalize_interval_period,
    _safe_get,
    _to_float,
    _utc_now_rfc3339,
    _epoch_to_rfc3339_utc,
    _dt_like_to_rfc3339_utc,
    _iter_history_rows,
)


# ============================================================
# Country Templates
# ============================================================
# Each entry:
#   index  : the primary benchmark index
#   stocks : top-5 constituents by market cap / avg daily
#            traded value (as of 2024-2025 reference date)
# Yahoo Finance symbols are used throughout.
# ============================================================

COUNTRY_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "US": {
        "name": "United States",
        "currency": "USD",
        "index": {"label": "S&P 500", "symbol": "^GSPC"},
        "stocks": [
            {"label": "Apple", "symbol": "AAPL"},
            {"label": "Microsoft", "symbol": "MSFT"},
            {"label": "NVIDIA", "symbol": "NVDA"},
            {"label": "Amazon", "symbol": "AMZN"},
            {"label": "Meta", "symbol": "META"},
        ],
    },
    "ID": {
        "name": "Indonesia",
        "currency": "IDR",
        "index": {"label": "IHSG", "symbol": "^JKSE"},
        "stocks": [
            {"label": "BBCA", "symbol": "BBCA.JK"},
            {"label": "BBRI", "symbol": "BBRI.JK"},
            {"label": "TLKM", "symbol": "TLKM.JK"},
            {"label": "BMRI", "symbol": "BMRI.JK"},
            {"label": "ASII", "symbol": "ASII.JK"},
        ],
    },
    "JP": {
        "name": "Japan",
        "currency": "JPY",
        "index": {"label": "Nikkei 225", "symbol": "^N225"},
        "stocks": [
            {"label": "Toyota", "symbol": "7203.T"},
            {"label": "Sony", "symbol": "6758.T"},
            {"label": "Mitsubishi UFJ", "symbol": "8306.T"},
            {"label": "Keyence", "symbol": "6861.T"},
            {"label": "NTT", "symbol": "9432.T"},
        ],
    },
    "CN": {
        "name": "China",
        "currency": "CNY",
        "index": {"label": "SSE Composite", "symbol": "000001.SS"},
        "stocks": [
            {"label": "Kweichow Moutai", "symbol": "600519.SS"},
            {"label": "ICBC", "symbol": "601398.SS"},
            {"label": "Ag Bank China", "symbol": "601288.SS"},
            {"label": "PetroChina", "symbol": "601857.SS"},
            {"label": "Sinopec", "symbol": "600028.SS"},
        ],
    },
    "HK": {
        "name": "Hong Kong",
        "currency": "HKD",
        "index": {"label": "Hang Seng", "symbol": "^HSI"},
        "stocks": [
            {"label": "Tencent", "symbol": "0700.HK"},
            {"label": "HSBC", "symbol": "0005.HK"},
            {"label": "Alibaba", "symbol": "9988.HK"},
            {"label": "China Mobile", "symbol": "0941.HK"},
            {"label": "Ping An", "symbol": "2318.HK"},
        ],
    },
    "GB": {
        "name": "United Kingdom",
        "currency": "GBP",
        "index": {"label": "FTSE 100", "symbol": "^FTSE"},
        "stocks": [
            {"label": "Shell", "symbol": "SHEL.L"},
            {"label": "AstraZeneca", "symbol": "AZN.L"},
            {"label": "HSBC", "symbol": "HSBA.L"},
            {"label": "Unilever", "symbol": "ULVR.L"},
            {"label": "BP", "symbol": "BP.L"},
        ],
    },
    "DE": {
        "name": "Germany",
        "currency": "EUR",
        "index": {"label": "DAX", "symbol": "^GDAXI"},
        "stocks": [
            {"label": "SAP", "symbol": "SAP.DE"},
            {"label": "Siemens", "symbol": "SIE.DE"},
            {"label": "Allianz", "symbol": "ALV.DE"},
            {"label": "Airbus", "symbol": "AIR.DE"},
            {"label": "Adidas", "symbol": "ADS.DE"},
        ],
    },
    "SG": {
        "name": "Singapore",
        "currency": "SGD",
        "index": {"label": "STI", "symbol": "^STI"},
        "stocks": [
            {"label": "DBS", "symbol": "D05.SI"},
            {"label": "OCBC", "symbol": "O39.SI"},
            {"label": "UOB", "symbol": "U11.SI"},
            {"label": "Singtel", "symbol": "Z74.SI"},
            {"label": "SIA", "symbol": "C6L.SI"},
        ],
    },
    "MY": {
        "name": "Malaysia",
        "currency": "MYR",
        "index": {"label": "KLCI", "symbol": "^KLSE"},
        "stocks": [
            {"label": "Maybank", "symbol": "1155.KL"},
            {"label": "Public Bank", "symbol": "1295.KL"},
            {"label": "Tenaga", "symbol": "5347.KL"},
            {"label": "CIMB", "symbol": "1023.KL"},
            {"label": "RHB Bank", "symbol": "1066.KL"},
        ],
    },
    "AU": {
        "name": "Australia",
        "currency": "AUD",
        "index": {"label": "ASX 200", "symbol": "^AXJO"},
        "stocks": [
            {"label": "CBA", "symbol": "CBA.AX"},
            {"label": "BHP", "symbol": "BHP.AX"},
            {"label": "CSL", "symbol": "CSL.AX"},
            {"label": "NAB", "symbol": "NAB.AX"},
            {"label": "WBC", "symbol": "WBC.AX"},
        ],
    },
}


# ============================================================
# Internal helpers
# ============================================================


def _build_session(proxy_url: Optional[str]) -> Optional[requests.Session]:
    """Create a requests.Session pre-configured with a proxy, or None."""
    if not proxy_url:
        return None
    session = requests.Session()
    session.proxies = {"http": proxy_url, "https": proxy_url}
    # Increase connection timeout slightly for remote proxies
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        }
    )
    return session


def _fetch_quote_raw(
    symbol: str,
    ticker_label: str,
    session: Optional[requests.Session] = None,
) -> QuoteSnapshot:
    """
    Low-level quote fetch using yfinance.
    Creates a Ticker with the given session (for proxy support),
    then tries fast_info → .info fallback.
    Returns a QuoteSnapshot (fields may be None on failure).
    """
    fetched_at = _utc_now_rfc3339()
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

    try:
        t = yf.Ticker(symbol, session=session) if session else yf.Ticker(symbol)

        # --- fast_info (lightweight) ---
        try:
            fi = getattr(t, "fast_info", None)
            if fi:
                try:
                    fi_dict = dict(fi)
                except Exception:
                    fi_dict = fi if isinstance(fi, dict) else {}

                out["currency"] = _safe_get(fi_dict, "currency") or out["currency"]
                out["exchange"] = _safe_get(fi_dict, "exchange") or out["exchange"]

                out["last_price"] = _to_float(
                    _safe_get(
                        fi_dict,
                        "last_price",
                        "lastPrice",
                        "regular_market_price",
                        "regularMarketPrice",
                    )
                )
                out["previous_close"] = _to_float(
                    _safe_get(
                        fi_dict,
                        "previous_close",
                        "previousClose",
                        "regular_market_previous_close",
                        "regularMarketPreviousClose",
                    )
                )
                out["open"] = _to_float(
                    _safe_get(
                        fi_dict, "open", "regular_market_open", "regularMarketOpen"
                    )
                )
                out["day_high"] = _to_float(
                    _safe_get(
                        fi_dict,
                        "day_high",
                        "dayHigh",
                        "regular_market_day_high",
                        "regularMarketDayHigh",
                    )
                )
                out["day_low"] = _to_float(
                    _safe_get(
                        fi_dict,
                        "day_low",
                        "dayLow",
                        "regular_market_day_low",
                        "regularMarketDayLow",
                    )
                )

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

        # --- .info fallback ---
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

    except Exception:
        pass

    # Compute derived change / change%
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


def _fetch_history_raw(
    symbol: str,
    ticker_label: str,
    interval: str = "1d",
    period: Optional[str] = "3mo",
    proxy_url: Optional[str] = None,
) -> List[PriceBar]:
    """
    Low-level history fetch using yf.download with optional proxy.
    Returns [] on any known Yahoo limitation instead of raising.
    """
    from typing import cast

    interval_n, period_n, _note = _normalize_interval_period(interval, period)
    use_period = period_n  # we always use period (no start/end in this helper)

    try:
        kwargs: Dict[str, Any] = dict(
            tickers=symbol,
            interval=interval_n,
            period=use_period,
            auto_adjust=False,
            progress=False,
            group_by="column",
            threads=False,
        )
        if proxy_url:
            kwargs["proxy"] = proxy_url

        data = yf.download(**kwargs)
    except Exception as exc:
        if _is_rate_limit_error(exc) or _is_no_price_data_error(exc):
            return []
        raise

    if data is None:
        return []

    empty_attr = getattr(data, "empty", None)
    try:
        is_empty = bool(empty_attr() if callable(empty_attr) else empty_attr)
        if is_empty:
            return []
    except Exception:
        pass

    bars: List[PriceBar] = []
    for idx, row in _iter_history_rows(data):
        dt_utc = _dt_like_to_rfc3339_utc(idx)
        if not dt_utc:
            continue

        def _get(*names: str) -> Any:
            for n in names:
                if isinstance(row, dict) and n in row:
                    return row[n]
            return None

        bars.append(
            PriceBar(
                ticker=ticker_label,
                symbol=symbol,
                interval=interval_n,
                datetime_utc=dt_utc,
                open=_to_float(_get("Open", "open")),
                high=_to_float(_get("High", "high")),
                low=_to_float(_get("Low", "low")),
                close=_to_float(_get("Close", "close")),
                adj_close=_to_float(_get("Adj Close", "AdjClose", "adj_close")),
                volume=_to_float(_get("Volume", "volume")),
            )
        )

    return bars


# ============================================================
# CountryMarketScraper
# ============================================================


class CountryMarketScraper:
    """
    Wraps yfinance to provide market overview data for a given country.

    Parameters
    ----------
    output_dir : str | None
        Where to save exported files (defaults to config.OUTPUT_DIR).
    proxies : list[str]
        Optional pool of HTTP/HTTPS proxy URLs.  Requests are distributed
        round-robin across this pool.  Supply as many as you like to
        minimise per-proxy rate-limit exposure.
        Example: ["http://10.0.0.1:3128", "http://10.0.0.2:3128"]
    max_workers : int
        Thread-pool size for concurrent quote fetches.  Default = 6
        (one per instrument).  Lower if you hit rate limits.
    """

    def __init__(
        self,
        output_dir: Optional[str] = None,
        proxies: Optional[List[str]] = None,
        max_workers: int = 6,
    ) -> None:
        self.output_dir: str = output_dir or (
            getattr(config, "OUTPUT_DIR", "output") if config else "output"
        )
        self._proxies: List[str] = proxies or []
        self._proxy_idx: int = 0
        self._proxy_lock: threading.Lock = threading.Lock()
        self.max_workers: int = max(1, max_workers)

        # Shared YahooFinancePriceScraper (no proxy) for export helpers
        self._base_scraper = YahooFinancePriceScraper(output_dir=self.output_dir)

    # ------------------------------------------------------------------
    # Proxy rotation
    # ------------------------------------------------------------------

    def set_proxies(self, proxies: List[str]) -> None:
        """Hot-swap the proxy pool at runtime (thread-safe)."""
        with self._proxy_lock:
            self._proxies = list(proxies)
            self._proxy_idx = 0

    def _next_proxy(self) -> Optional[str]:
        """Round-robin proxy selection.  Thread-safe."""
        with self._proxy_lock:
            if not self._proxies:
                return None
            proxy = self._proxies[self._proxy_idx % len(self._proxies)]
            self._proxy_idx += 1
            return proxy

    # ------------------------------------------------------------------
    # Country / template helpers
    # ------------------------------------------------------------------

    def list_countries(self) -> List[Tuple[str, str]]:
        """Return [(code, display_name), ...] sorted by display name."""
        return sorted(
            [(code, info["name"]) for code, info in COUNTRY_TEMPLATES.items()],
            key=lambda x: x[1],
        )

    def get_template(self, country_code: str) -> Optional[Dict[str, Any]]:
        """Return the template dict for a country code, or None."""
        return COUNTRY_TEMPLATES.get(country_code.upper())

    def get_instruments(self, country_code: str) -> List[Tuple[str, str, str]]:
        """
        Return a flat list of (label, symbol, instrument_type) for the country.
        instrument_type is "index" or "stock".
        Index is always first.
        """
        tmpl = self.get_template(country_code)
        if not tmpl:
            return []

        result: List[Tuple[str, str, str]] = []
        idx = tmpl["index"]
        result.append((idx["label"], idx["symbol"], "index"))
        for s in tmpl.get("stocks", []):
            result.append((s["label"], s["symbol"], "stock"))
        return result

    def get_index(self, country_code: str) -> Optional[Tuple[str, str]]:
        """Return (label, symbol) for the country's benchmark index."""
        tmpl = self.get_template(country_code)
        if not tmpl:
            return None
        idx = tmpl["index"]
        return idx["label"], idx["symbol"]

    # ------------------------------------------------------------------
    # Concurrent quote fetching
    # ------------------------------------------------------------------

    def fetch_all_quotes(self, country_code: str) -> Dict[str, Optional[QuoteSnapshot]]:
        """
        Concurrently fetch current quote snapshots for all 6 instruments
        (1 index + 5 stocks) for the given country.

        Returns a dict mapping label → QuoteSnapshot (or None on error).
        Preserves insertion order (index first).
        """
        instruments = self.get_instruments(country_code)
        if not instruments:
            return {}

        results: Dict[str, Optional[QuoteSnapshot]] = {
            label: None for label, _, _ in instruments
        }

        def _worker(label: str, symbol: str) -> Tuple[str, Optional[QuoteSnapshot]]:
            proxy = self._next_proxy()
            session = _build_session(proxy)
            try:
                q = _fetch_quote_raw(symbol, label, session=session)
                return label, q
            except Exception:
                return label, None

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {
                pool.submit(_worker, label, symbol): label
                for label, symbol, _ in instruments
            }
            for fut in as_completed(futures):
                try:
                    lbl, q = fut.result()
                    results[lbl] = q
                except Exception:
                    pass  # label stays None

        return results

    def fetch_quote(self, symbol: str, ticker_label: str) -> Optional[QuoteSnapshot]:
        """Fetch a single quote snapshot (with proxy rotation)."""
        proxy = self._next_proxy()
        session = _build_session(proxy)
        try:
            return _fetch_quote_raw(symbol, ticker_label, session=session)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # History fetching
    # ------------------------------------------------------------------

    def fetch_history(
        self,
        symbol: str,
        ticker_label: str,
        interval: str = "1d",
        period: str = "3mo",
    ) -> List[PriceBar]:
        """
        Fetch OHLCV history bars.  Proxy rotation is applied.
        Returns [] on rate-limit / known Yahoo restrictions.
        """
        proxy = self._next_proxy()
        try:
            return _fetch_history_raw(
                symbol=symbol,
                ticker_label=ticker_label,
                interval=interval,
                period=period,
                proxy_url=proxy,
            )
        except Exception:
            return []

    def fetch_all_histories(
        self,
        country_code: str,
        interval: str = "1d",
        period: str = "3mo",
    ) -> Dict[str, List[PriceBar]]:
        """
        Concurrently fetch OHLCV history for all instruments in a country.
        Returns dict mapping label → list[PriceBar].
        """
        instruments = self.get_instruments(country_code)
        if not instruments:
            return {}

        results: Dict[str, List[PriceBar]] = {label: [] for label, _, _ in instruments}

        def _worker(label: str, symbol: str) -> Tuple[str, List[PriceBar]]:
            proxy = self._next_proxy()
            bars = _fetch_history_raw(
                symbol=symbol,
                ticker_label=label,
                interval=interval,
                period=period,
                proxy_url=proxy,
            )
            return label, bars

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {
                pool.submit(_worker, label, symbol): label
                for label, symbol, _ in instruments
            }
            for fut in as_completed(futures):
                try:
                    lbl, bars = fut.result()
                    results[lbl] = bars
                except Exception:
                    pass

        return results

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_country_snapshot(
        self,
        country_code: str,
        quotes: Dict[str, Optional[QuoteSnapshot]],
        histories: Optional[Dict[str, List[PriceBar]]] = None,
        fmt: str = "json",
        interval: str = "1d",
        period: str = "3mo",
    ) -> Optional[str]:
        """
        Save a country market snapshot to output_dir/<country>_market.json.

        Returns the file path on success, or None on failure.
        """
        import json

        os.makedirs(self.output_dir, exist_ok=True)

        payload: Dict[str, Any] = {
            "country_code": country_code.upper(),
            "country_name": (self.get_template(country_code) or {}).get("name", ""),
            "fetched_at_utc": _utc_now_rfc3339(),
            "interval": interval,
            "period": period,
            "quotes": {},
            "histories": {},
        }

        for label, q in quotes.items():
            payload["quotes"][label] = asdict(q) if q else None

        if histories:
            for label, bars in histories.items():
                payload["histories"][label] = [asdict(b) for b in bars]

        fname = f"{country_code.upper()}_market_snapshot.json"
        fpath = os.path.join(self.output_dir, fname)
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            return fpath
        except Exception:
            return None


# ============================================================
# Convenience accessors (used by UI)
# ============================================================


def get_country_display_list() -> List[str]:
    """
    Returns display strings like 'US – United States' for use in
    UI dropdowns, preserving COUNTRY_TEMPLATES insertion order.
    """
    return [f"{code} – {info['name']}" for code, info in COUNTRY_TEMPLATES.items()]


def parse_country_code(display: str) -> str:
    """
    Extract the 2-letter country code from a display string
    like 'US – United States'.
    """
    return (
        display.split("–")[0].strip().upper()
        if "–" in display
        else display.strip().upper()
    )


def format_change(change: Optional[float], change_pct: Optional[float]) -> str:
    """Return a formatted '+1.23 (+0.45%)' string, or '—' if unavailable."""
    if change is None and change_pct is None:
        return "—"
    parts = []
    if change is not None:
        parts.append(f"{change:+.4g}")
    if change_pct is not None:
        parts.append(f"({change_pct:+.2f}%)")
    return " ".join(parts)


def format_price(price: Optional[float], currency: Optional[str] = None) -> str:
    """Format a price value for display."""
    if price is None:
        return "—"
    if abs(price) >= 10_000:
        formatted = f"{price:,.0f}"
    elif abs(price) >= 100:
        formatted = f"{price:,.2f}"
    else:
        formatted = f"{price:.4f}"
    if currency:
        return f"{formatted} {currency}"
    return formatted
