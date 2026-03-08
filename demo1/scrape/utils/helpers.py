# ============================================================
# Economic Calendar Scraper - Utility Helpers
# ============================================================

from __future__ import annotations

import csv
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ── Timezone Constants ───────────────────────────────────────
TZ_UTC = timezone.utc
TZ_WIB = ZoneInfo("Asia/Jakarta")  # Indonesia (WIB, UTC+7)
TZ_EST = ZoneInfo("America/New_York")  # US Eastern

# ── Logger Factory ───────────────────────────────────────────

_LOGGERS: dict[str, logging.Logger] = {}


def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    """
    Return a named logger with a consistent format.
    Re-uses the same logger instance if already created.
    """
    if name in _LOGGERS:
        return _LOGGERS[name]

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)

    logger.propagate = False
    _LOGGERS[name] = logger
    return logger


def add_file_handler(logger: logging.Logger, log_path: str) -> None:
    """Attach a rotating file handler to *logger*."""
    from logging.handlers import RotatingFileHandler

    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(file_handler)


# ── HTTP Session Factory ─────────────────────────────────────


def build_session(
    headers: Optional[dict] = None,
    retries: int = 3,
    backoff_factor: float = 1.5,
    status_forcelist: tuple = (429, 500, 502, 503, 504),
    proxies: Optional[dict] = None,
) -> requests.Session:
    """
    Create a ``requests.Session`` pre-configured with:

    * automatic retries with exponential back-off
    * custom default headers
    * optional proxy support

    Parameters
    ----------
    headers:
        Extra HTTP headers merged into every request.
    retries:
        Number of retry attempts before raising an exception.
    backoff_factor:
        Exponential back-off multiplier between retry attempts.
    status_forcelist:
        HTTP status codes that should trigger a retry.
    proxies:
        Dict of ``{"http": "...", "https": "..."}`` proxy URLs.
    """
    session = requests.Session()

    retry = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=list(status_forcelist),
        allowed_methods=["GET", "POST"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    if headers:
        session.headers.update(headers)

    if proxies:
        session.proxies.update(proxies)

    return session


def safe_get(
    session: requests.Session,
    url: str,
    params: Optional[dict] = None,
    timeout: int = 30,
    delay: float = 2.0,
    logger: Optional[logging.Logger] = None,
) -> Optional[requests.Response]:
    """
    Perform a GET request and return the response, or *None* on failure.

    A polite ``delay`` is applied *before* the request so this can be
    called in a tight loop without hammering servers.
    """
    log = logger or get_logger("helpers")
    time.sleep(delay)
    try:
        resp = session.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        log.debug("GET %s → %d", url, resp.status_code)
        return resp
    except requests.HTTPError as exc:
        log.warning("HTTP error on GET %s: %s", url, exc)
    except requests.ConnectionError as exc:
        log.warning("Connection error on GET %s: %s", url, exc)
    except requests.Timeout:
        log.warning("Timeout on GET %s", url)
    except Exception as exc:  # noqa: BLE001
        log.error("Unexpected error on GET %s: %s", url, exc)
    return None


def safe_post(
    session: requests.Session,
    url: str,
    data: Optional[dict] = None,
    json_body: Optional[dict] = None,
    timeout: int = 30,
    delay: float = 2.0,
    logger: Optional[logging.Logger] = None,
) -> Optional[requests.Response]:
    """
    Perform a POST request and return the response, or *None* on failure.
    """
    log = logger or get_logger("helpers")
    time.sleep(delay)
    try:
        resp = session.post(url, data=data, json=json_body, timeout=timeout)
        resp.raise_for_status()
        log.debug("POST %s → %d", url, resp.status_code)
        return resp
    except requests.HTTPError as exc:
        log.warning("HTTP error on POST %s: %s", url, exc)
    except requests.ConnectionError as exc:
        log.warning("Connection error on POST %s: %s", url, exc)
    except requests.Timeout:
        log.warning("Timeout on POST %s", url)
    except Exception as exc:  # noqa: BLE001
        log.error("Unexpected error on POST %s: %s", url, exc)
    return None


# ── Date / Time Utilities ─────────────────────────────────────


def today_str(tz: ZoneInfo | timezone = TZ_WIB) -> str:
    """Return today's date as 'YYYY-MM-DD' in the given timezone."""
    return datetime.now(tz).strftime("%Y-%m-%d")


def now_dt(tz: ZoneInfo | timezone = TZ_WIB) -> datetime:
    """Return the current datetime in the given timezone."""
    return datetime.now(tz)


def date_range(
    start: str,
    end: str,
    fmt: str = "%Y-%m-%d",
) -> list[str]:
    """
    Return a list of date strings between *start* and *end* (inclusive).

    >>> date_range("2025-03-01", "2025-03-03")
    ['2025-03-01', '2025-03-02', '2025-03-03']
    """
    start_dt = datetime.strptime(start, fmt)
    end_dt = datetime.strptime(end, fmt)
    days = (end_dt - start_dt).days
    return [(start_dt + timedelta(days=i)).strftime(fmt) for i in range(days + 1)]


def get_scrape_window(
    days_back: int = 1,
    days_ahead: int = 7,
    tz: ZoneInfo | timezone = TZ_WIB,
    fmt: str = "%Y-%m-%d",
) -> tuple[str, str]:
    """
    Return a ``(date_from, date_to)`` window relative to today.

    Parameters
    ----------
    days_back:
        Number of days before today to include.
    days_ahead:
        Number of days after today to include.
    tz:
        Timezone to use when determining "today".
    fmt:
        strftime format for the returned strings.

    Returns
    -------
    Tuple of ``(date_from_str, date_to_str)``.
    """
    today = datetime.now(tz).date()
    date_from = today - timedelta(days=days_back)
    date_to = today + timedelta(days=days_ahead)
    return date_from.strftime(fmt), date_to.strftime(fmt)


def parse_ff_datetime(iso_str: str) -> Optional[datetime]:
    """
    Parse the ISO-8601 datetime strings emitted by the ForexFactory
    JSON API (e.g. ``"2025-03-06T08:30:00-05:00"``) into a UTC-aware
    ``datetime`` object.
    """
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.astimezone(TZ_UTC)
    except (ValueError, TypeError):
        return None


def format_display_datetime(
    dt: Optional[datetime],
    tz: ZoneInfo | timezone = TZ_WIB,
) -> tuple[str, str]:
    """
    Convert a UTC-aware datetime to (date_str, time_str) in *tz*.

    Returns ``('', '')`` when *dt* is ``None``.
    """
    if dt is None:
        return "", ""
    local = dt.astimezone(tz)
    return local.strftime("%Y-%m-%d"), local.strftime("%H:%M")


# ── Category Resolution ──────────────────────────────────────


def resolve_category(title: str, categories: dict[str, str]) -> str:
    """
    Match a lower-cased *title* against the keyword → category mapping.
    Returns the first match, or empty string if none found.
    """
    title_lower = title.lower()
    for keyword, category in categories.items():
        if keyword in title_lower:
            return category
    return ""


# ── Region Lookup ─────────────────────────────────────────────

CURRENCY_TO_REGION: dict[str, str] = {
    "USD": "United States",
    "IDR": "Indonesia",
    "EUR": "Euro Area",
    "GBP": "United Kingdom",
    "JPY": "Japan",
    "AUD": "Australia",
    "NZD": "New Zealand",
    "CAD": "Canada",
    "CHF": "Switzerland",
    "CNY": "China",
    "KRW": "South Korea",
    "SGD": "Singapore",
    "MYR": "Malaysia",
    "THB": "Thailand",
    "PHP": "Philippines",
    "VND": "Vietnam",
}

CURRENCY_TO_COUNTRY: dict[str, str] = {
    "USD": "US",
    "IDR": "ID",
    "EUR": "EU",
    "GBP": "GB",
    "JPY": "JP",
    "AUD": "AU",
    "NZD": "NZ",
    "CAD": "CA",
    "CHF": "CH",
    "CNY": "CN",
    "KRW": "KR",
    "SGD": "SG",
    "MYR": "MY",
    "THB": "TH",
    "PHP": "PH",
    "VND": "VN",
}


def currency_to_region(currency: str) -> str:
    return CURRENCY_TO_REGION.get(currency.upper(), currency)


def currency_to_country(currency: str) -> str:
    return CURRENCY_TO_COUNTRY.get(currency.upper(), "")


# ── Clean-up Helpers ─────────────────────────────────────────


def clean_value(raw: str) -> str:
    """
    Strip whitespace and normalise common placeholder strings to ''.
    """
    if raw is None:
        return ""
    cleaned = str(raw).strip().replace("\xa0", "").replace("\u200b", "")
    if cleaned in ("-", "—", "N/A", "n/a", "na", "NA", "null", "None"):
        return ""
    return cleaned


def deduplicate_events(events: list, key_fn=None) -> list:
    """
    Remove duplicate events from *events* using a composite key.

    Default key: (date, currency, title)
    The first occurrence of each key is kept; later duplicates are dropped.
    """
    if key_fn is None:

        def _default_key(e):
            return (
                getattr(e, "date", ""),
                getattr(e, "currency", ""),
                getattr(e, "title", "").strip().lower(),
            )

        key_callable = _default_key
    else:
        key_callable = key_fn

    seen: set = set()
    unique: list = []
    for event in events:
        k = key_callable(event)
        if k not in seen:
            seen.add(k)
            unique.append(event)
    return unique


def sort_events(events: list) -> list:
    """
    Sort events chronologically by (date, time).
    Events without a time are placed at the start of their date.
    """

    def sort_key(e):
        date = getattr(e, "date", "")
        time_ = getattr(e, "time", "") or "00:00"
        return (date, time_)

    return sorted(events, key=sort_key)


# ── File Export ──────────────────────────────────────────────


def ensure_output_dir(path: str) -> Path:
    """Create *path* (and any missing parents) if it doesn't exist."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_to_json(
    events: list,
    filepath: str,
    include_raw: bool = False,
    indent: int = 2,
) -> None:
    """
    Serialise a list of ``EconomicEvent`` objects to a JSON file.

    Parameters
    ----------
    events:
        List of EconomicEvent instances.
    filepath:
        Destination file path (parent directories will be created).
    include_raw:
        Whether to include the ``raw`` field in the output.
    indent:
        JSON indentation level.
    """
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)

    records = [
        e.to_dict(include_raw=include_raw)
        if hasattr(e, "to_dict")
        else (e if isinstance(e, dict) else vars(e))
        for e in events
    ]
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=indent, default=str)

    logger = get_logger("helpers")
    logger.info("💾 Saved %d events → %s", len(records), filepath)


def save_to_csv(
    events: list,
    filepath: str,
    exclude_fields: Optional[list[str]] = None,
) -> None:
    """
    Write a list of ``EconomicEvent`` objects to a CSV file.

    Parameters
    ----------
    events:
        List of EconomicEvent instances.
    filepath:
        Destination file path (parent directories will be created).
    exclude_fields:
        Field names to omit from the CSV (e.g. ['raw', 'datetime_utc']).
    """
    if not events:
        return

    if exclude_fields is None:
        exclude_fields = ["raw", "impact_emoji"]

    Path(filepath).parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for e in events:
        d = (
            e.to_dict()
            if hasattr(e, "to_dict")
            else (e if isinstance(e, dict) else vars(e))
        )
        for field in exclude_fields:
            d.pop(field, None)
        # Convert datetime objects to ISO strings
        for k, v in d.items():
            if isinstance(v, datetime):
                d[k] = v.isoformat()
        rows.append(d)

    if not rows:
        return

    fieldnames = list(rows[0].keys())
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    logger = get_logger("helpers")
    logger.info("💾 Saved %d events → %s", len(rows), filepath)


def save_events(
    events: list,
    output_dir: str,
    filename_prefix: str,
    fmt: str = "both",
) -> dict[str, str]:
    """
    Convenience wrapper that saves events as JSON and/or CSV.

    Parameters
    ----------
    events:
        List of EconomicEvent instances.
    output_dir:
        Directory where files will be written.
    filename_prefix:
        File name without extension, e.g. ``"forexfactory_usd"``.
    fmt:
        ``'json'``, ``'csv'``, or ``'both'``.

    Returns
    -------
    Dict mapping format name to output file path.
    """
    ensure_output_dir(output_dir)
    paths: dict[str, str] = {}

    if fmt in ("json", "both"):
        json_path = os.path.join(output_dir, f"{filename_prefix}.json")
        save_to_json(events, json_path)
        paths["json"] = json_path

    if fmt in ("csv", "both"):
        csv_path = os.path.join(output_dir, f"{filename_prefix}.csv")
        save_to_csv(events, csv_path)
        paths["csv"] = csv_path

    return paths


# ── Summary / Reporting ──────────────────────────────────────


def print_summary_table(events: list, title: str = "Economic Calendar") -> None:
    """
    Print a simple text summary of scraped events to stdout.
    Grouped by impact level and currency.
    """
    from collections import Counter

    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"  Total events: {len(events)}")
    print(f"{'=' * 60}")

    impact_counts: Counter = Counter()
    currency_counts: Counter = Counter()

    for e in events:
        impact_counts[getattr(e, "impact", "Unknown")] += 1
        currency_counts[getattr(e, "currency", "Unknown")] += 1

    print("\n  By Impact:")
    for impact, count in sorted(impact_counts.items()):
        emoji = {"High": "🔴", "Medium": "🟡", "Low": "⚪"}.get(impact, "❔")
        print(f"    {emoji} {impact:8}: {count}")

    print("\n  By Currency:")
    for cur, count in sorted(currency_counts.items()):
        print(f"    {cur:6}: {count}")

    high_impact = [e for e in events if getattr(e, "impact", "") == "High"]
    if high_impact:
        print(f"\n  🔴 High Impact Events ({len(high_impact)}):")
        for e in high_impact[:15]:
            print(
                f"    • {getattr(e, 'date', ''):<12} "
                f"{getattr(e, 'currency', ''):4} "
                f"{getattr(e, 'title', '')}"
            )
        if len(high_impact) > 15:
            print(f"    ... and {len(high_impact) - 15} more")

    print(f"{'=' * 60}\n")
