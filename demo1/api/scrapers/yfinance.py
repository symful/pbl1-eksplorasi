from datetime import datetime, timezone
from typing import Optional, Any

import yfinance as yf

from api.models.schemas import PriceBar, QuoteSnapshot


def utc_now_rfc3339() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
        if f != f:
            return None
        return f
    except Exception:
        return None


def safe_get(d: dict, *keys: str) -> Any:
    if not isinstance(d, dict):
        return None
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def epoch_to_rfc3339(v: Any) -> Optional[str]:
    try:
        if v is None:
            return None
        dt = datetime.fromtimestamp(int(v), tz=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    except Exception:
        return None


def dt_to_rfc3339(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, datetime):
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        else:
            v = v.astimezone(timezone.utc)
        return v.isoformat().replace("+00:00", "Z")

    to_py = getattr(v, "to_pydatetime", None)
    if callable(to_py):
        try:
            return dt_to_rfc3339(to_py())
        except Exception:
            return None

    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            s = s.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            return dt.isoformat().replace("+00:00", "Z")
        except Exception:
            return None
    return None


def normalize_interval_period(interval: str, period: Optional[str]) -> tuple[str, Optional[str]]:
    interval = (interval or "").strip() or "1d"
    period = (period or "").strip() or None

    if interval == "1m":
        if period not in ("1d", "5d"):
            period = "5d"

    if interval in ("5m", "15m", "30m", "60m", "90m", "1h"):
        if period in ("10y", "max"):
            period = "2y"

    return interval, period


def iter_history_rows(history_obj: Any) -> list[tuple[Any, dict]]:
    if history_obj is None:
        return []

    rows = []
    it = getattr(history_obj, "iterrows", None)
    if callable(it):
        for idx, row in it():
            row_dict = {}
            to_dict = getattr(row, "to_dict", None)
            if callable(to_dict):
                try:
                    row_dict = dict(to_dict())
                except Exception:
                    pass
            else:
                try:
                    row_dict = dict(row)
                except Exception:
                    pass

            flat_dict = {}
            for k, v in row_dict.items():
                if isinstance(k, tuple) and len(k) > 0:
                    flat_dict[str(k[0])] = v
                else:
                    flat_dict[str(k)] = v

            rows.append((idx, flat_dict))
        return rows

    if isinstance(history_obj, dict):
        timestamps = set()
        for col_name, inner in history_obj.items():
            if isinstance(inner, dict):
                for k, v in inner.items():
                    if isinstance(v, dict):
                        timestamps.update(v.keys())
                    else:
                        timestamps.add(k)

        for ts in sorted(list(timestamps), key=lambda x: str(x)):
            row_dict = {}
            for col_name, inner in history_obj.items():
                if isinstance(inner, dict):
                    found = False
                    for tk, v in inner.items():
                        if isinstance(v, dict) and ts in v:
                            row_dict[col_name] = v[ts]
                            found = True
                    if not found and ts in inner:
                        row_dict[col_name] = inner[ts]
            rows.append((ts, row_dict))
        return rows

    return []


class YahooFinanceScraper:
    def __init__(self, proxy: Optional[str] = None):
        self.proxy = proxy

    def _make_ticker(self, symbol: str):
        if self.proxy:
            try:
                import requests

                session = requests.Session()
                session.proxies = {"http": self.proxy, "https": self.proxy}
                session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
                return yf.Ticker(symbol, session=session)
            except Exception:
                pass
        return yf.Ticker(symbol)

    def fetch_quote(self, symbol: str, ticker_label: str) -> QuoteSnapshot:
        fetched_at = utc_now_rfc3339()
        t = self._make_ticker(symbol)

        out = {
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
            fi = getattr(t, "fast_info", None)
            if fi:
                try:
                    fi_dict = dict(fi)
                except Exception:
                    fi_dict = fi if isinstance(fi, dict) else {}

                out["currency"] = safe_get(fi_dict, "currency")
                out["exchange"] = safe_get(fi_dict, "exchange")

                last = safe_get(fi_dict, "last_price", "lastPrice", "regular_market_price", "regularMarketPrice")
                prev = safe_get(fi_dict, "previous_close", "previousClose", "regular_market_previous_close", "regularMarketPreviousClose")
                opn = safe_get(fi_dict, "open", "regular_market_open", "regularMarketOpen")
                hi = safe_get(fi_dict, "day_high", "dayHigh", "regular_market_day_high", "regularMarketDayHigh")
                lo = safe_get(fi_dict, "day_low", "dayLow", "regular_market_day_low", "regularMarketDayLow")

                out["last_price"] = to_float(last)
                out["previous_close"] = to_float(prev)
                out["open"] = to_float(opn)
                out["day_high"] = to_float(hi)
                out["day_low"] = to_float(lo)

                mt = safe_get(fi_dict, "last_market_time", "lastMarketTime", "regular_market_time", "regularMarketTime")
                out["market_time_utc"] = epoch_to_rfc3339(mt)
        except Exception:
            pass

        try:
            info = getattr(t, "info", None) or {}
            if isinstance(info, dict) and info:
                out["currency"] = out["currency"] or safe_get(info, "currency")
                out["exchange"] = out["exchange"] or safe_get(info, "exchange")
                out["quote_type"] = safe_get(info, "quoteType")

                if out["last_price"] is None:
                    out["last_price"] = to_float(safe_get(info, "regularMarketPrice", "currentPrice"))
                if out["previous_close"] is None:
                    out["previous_close"] = to_float(safe_get(info, "regularMarketPreviousClose", "previousClose"))
                if out["open"] is None:
                    out["open"] = to_float(safe_get(info, "regularMarketOpen", "open"))
                if out["day_high"] is None:
                    out["day_high"] = to_float(safe_get(info, "regularMarketDayHigh", "dayHigh"))
                if out["day_low"] is None:
                    out["day_low"] = to_float(safe_get(info, "regularMarketDayLow", "dayLow"))

                if out["market_time_utc"] is None:
                    out["market_time_utc"] = epoch_to_rfc3339(safe_get(info, "regularMarketTime"))
        except Exception:
            pass

        last_p = out["last_price"]
        prev_c = out["previous_close"]
        if isinstance(last_p, (int, float)) and isinstance(prev_c, (int, float)) and prev_c != 0:
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
    ) -> list[PriceBar]:
        interval_n, period_n = normalize_interval_period(interval, period)
        use_period = None if start else period_n

        try:
            dl_kwargs = dict(
                tickers=symbol,
                interval=interval_n,
                period=use_period,
                start=start,
                end=end,
                progress=False,
                threads=False,
            )
            if self.proxy:
                dl_kwargs["proxy"] = self.proxy
            data = yf.download(**dl_kwargs)
        except Exception:
            return []

        if data is None:
            return []

        empty_attr = getattr(data, "empty", None)
        try:
            if callable(empty_attr):
                if empty_attr():
                    return []
            elif isinstance(empty_attr, bool) and empty_attr:
                return []
        except Exception:
            pass

        bars = []
        for idx, row in iter_history_rows(data):
            dt_utc = dt_to_rfc3339(idx)
            if not dt_utc:
                continue

            def get_col(*names) -> Any:
                for n in names:
                    if isinstance(row, dict) and n in row:
                        return row.get(n)
                return None

            o = to_float(get_col("Open", "open"))
            h = to_float(get_col("High", "high"))
            l = to_float(get_col("Low", "low"))
            c = to_float(get_col("Close", "close"))
            ac = to_float(get_col("Adj Close", "AdjClose", "adj_close", "adjclose"))
            v = to_float(get_col("Volume", "volume"))

            bars.append(
                PriceBar(
                    ticker=ticker_label,
                    symbol=symbol,
                    interval=interval_n,
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


def fetch_quote(symbol: str, ticker_label: str, proxy: Optional[str] = None) -> QuoteSnapshot:
    scraper = YahooFinanceScraper(proxy=proxy)
    return scraper.fetch_quote(symbol, ticker_label)


def fetch_history(
    symbol: str,
    ticker_label: str,
    interval: str = "1d",
    period: Optional[str] = "3mo",
    start: Optional[str] = None,
    end: Optional[str] = None,
    proxy: Optional[str] = None,
) -> list[PriceBar]:
    scraper = YahooFinanceScraper(proxy=proxy)
    return scraper.fetch_history(
        symbol=symbol,
        ticker_label=ticker_label,
        interval=interval,
        period=period,
        start=start,
        end=end,
    )
