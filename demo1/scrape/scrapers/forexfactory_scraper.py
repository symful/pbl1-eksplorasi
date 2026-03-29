# ============================================================
# Economic Calendar Scraper - ForexFactory
# ============================================================
#
# Data Source : https://nfs.faireconomy.media/ff_calendar_thisweek.json
# Coverage    : USD (and other major currencies — IDR not available)
# Auth        : None required
# Rate Limit  : Be polite; 2-second delay between requests
#
# ForexFactory publishes an official JSON feed for their economic
# calendar. The feed covers the current week and (when available)
# the next week.  Each event record contains:
#
#   title    – event name
#   country  – ISO-like currency code, e.g. "USD", "EUR", "JPY"
#   date     – ISO-8601 datetime string with UTC offset
#   impact   – "High" | "Medium" | "Low" | "Holiday"
#   forecast – analyst consensus (may be empty)
#   previous – previous period value (may be empty)
#
# Note: The "actual" field is NOT present in the feed until the
# event has been released; it simply won't appear in the JSON.
# ============================================================

from __future__ import annotations

import sys
import os
from datetime import datetime
from typing import Optional

# Allow running this file directly (python scrapers/forexfactory_scraper.py)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
from models.economic_event import EconomicEvent
from utils.helpers import (
    build_session,
    clean_value,
    currency_to_country,
    currency_to_region,
    format_display_datetime,
    get_logger,
    get_scrape_window,
    parse_ff_datetime,
    resolve_category,
    safe_get,
    sort_events,
    TZ_WIB,
)

log = get_logger("forexfactory", config.LOG_LEVEL)


def _silent_logger():
    import logging
    return logging.getLogger("forexfactory.silent")


# ── Constants ─────────────────────────────────────────────────

SOURCE_NAME = "forexfactory"

# ForexFactory uses "Holiday" as an impact level — map it to Low.
_IMPACT_MAP: dict[str, str] = {
    "High": "High",
    "Medium": "Medium",
    "Low": "Low",
    "Holiday": "Low",
    "": "Low",
}


# ── Main Scraper Class ────────────────────────────────────────


class ForexFactoryScraper:
    """
    Scrapes the ForexFactory economic calendar JSON feed.

    Fetches both the *this-week* and *next-week* feeds, normalises
    each record into an ``EconomicEvent``, and filters the results
    to only the currencies specified in ``config.FF_TARGET_CURRENCIES``
    (default: ``["USD"]``).

    Usage
    -----
    >>> scraper = ForexFactoryScraper()
    >>> events = scraper.fetch()
    >>> for event in events:
    ...     print(event)
    """

    def __init__(
        self,
        target_currencies: Optional[list[str]] = None,
        impact_filter: Optional[list[str]] = None,
    ) -> None:
        """
        Parameters
        ----------
        target_currencies:
            List of currency codes to keep, e.g. ``["USD"]``.
            Defaults to ``config.FF_TARGET_CURRENCIES``.
        impact_filter:
            List of impact levels to keep: ``["High", "Medium", "Low"]``.
            Pass ``None`` (default) to keep all levels.
        """
        self.target_currencies: list[str] = [
            c.upper() for c in (target_currencies or config.FF_TARGET_CURRENCIES)
        ]
        self.impact_filter: Optional[list[str]] = impact_filter

        self._session = build_session(
            headers=config.DEFAULT_HEADERS,
            retries=config.MAX_RETRIES,
            proxies=config.PROXIES,
        )

    # ── Public API ────────────────────────────────────────────

    def fetch(self) -> list[EconomicEvent]:
        """
        Fetch and return economic events from ForexFactory.

        Tries the *this-week* feed first, then attempts the *next-week*
        feed (which may return 404 if the server has not yet published it).

        Returns
        -------
        Sorted, deduplicated list of ``EconomicEvent`` objects.
        """
        all_events: list[EconomicEvent] = []

        for label, url in [
            ("this_week", config.FF_THIS_WEEK),
            ("next_week", config.FF_NEXT_WEEK),
        ]:
            log.info("📡 Fetching ForexFactory %s feed…", label)
            events = self._fetch_feed(url, optional=(label == "next_week"))
            if events is not None:
                log.info("  ✅ %d raw events from %s", len(events), label)
                all_events.extend(events)
            else:
                if label == "next_week":
                    log.info("  —   next_week feed not yet available (skipping).")
                else:
                    log.warning("  ⚠️  No data returned for %s", label)

        if not all_events:
            log.error("ForexFactory: no events fetched from any feed.")
            return []

        # Filter by currency
        filtered = self._filter_currencies(all_events)
        log.info(
            "ForexFactory: %d events after currency filter %s",
            len(filtered),
            self.target_currencies,
        )

        # Filter by impact level (if requested)
        if self.impact_filter:
            filtered = [e for e in filtered if e.impact in self.impact_filter]
            log.info(
                "ForexFactory: %d events after impact filter %s",
                len(filtered),
                self.impact_filter,
            )

        return sort_events(filtered)

    def fetch_high_impact(self) -> list[EconomicEvent]:
        """Convenience method — returns only High-impact USD events."""
        return [e for e in self.fetch() if e.impact == "High"]

    # ── Internal Helpers ──────────────────────────────────────

    def _fetch_feed(
        self, url: str, optional: bool = False
    ) -> Optional[list[EconomicEvent]]:
        """
        Download one JSON feed URL and parse it into EconomicEvent objects.

        Parameters
        ----------
        url:
            The feed URL to fetch.
        optional:
            When ``True``, HTTP errors (e.g. 404 for next_week) are logged
            at DEBUG level instead of WARNING.

        Returns ``None`` on network or parse errors.
        """
        resp = safe_get(
            self._session,
            url,
            timeout=config.REQUEST_TIMEOUT,
            delay=config.REQUEST_DELAY,
            logger=log if not optional else _silent_logger(),
        )
        if resp is None:
            return None

        try:
            raw_list: list[dict] = resp.json()
        except ValueError as exc:
            log.error("ForexFactory: failed to parse JSON from %s — %s", url, exc)
            return None

        events: list[EconomicEvent] = []
        for raw in raw_list:
            event = self._parse_record(raw)
            if event is not None:
                events.append(event)

        return events

    def _parse_record(self, raw: dict) -> Optional[EconomicEvent]:
        """
        Convert a single raw JSON record from the FF feed into an
        ``EconomicEvent``.  Returns ``None`` for malformed records.
        """
        try:
            currency: str = clean_value(raw.get("country", "")).upper()
            title: str = clean_value(raw.get("title", ""))
            impact_raw: str = clean_value(raw.get("impact", ""))
            impact: str = _IMPACT_MAP.get(impact_raw, "Low")
            date_iso: str = clean_value(raw.get("date", ""))
            forecast: str = clean_value(raw.get("forecast", ""))
            previous: str = clean_value(raw.get("previous", ""))
            # "actual" key is only present after an event has been released
            actual: str = clean_value(raw.get("actual", ""))

            if not title or not date_iso:
                log.debug(
                    "ForexFactory: skipping record with missing title/date: %s", raw
                )
                return None

            # Parse datetime and convert to WIB (UTC+7) for display
            datetime_utc = parse_ff_datetime(date_iso)
            date_str, time_str = format_display_datetime(datetime_utc, tz=TZ_WIB)

            # Fallback: if datetime parsing fails, extract date from the ISO string
            if not date_str:
                date_str = date_iso[:10] if len(date_iso) >= 10 else date_iso

            category = resolve_category(title, config.EVENT_CATEGORIES)
            country = currency_to_country(currency)
            region = currency_to_region(currency)

            return EconomicEvent(
                source=SOURCE_NAME,
                event_id="",
                date=date_str,
                time=time_str,
                datetime_utc=datetime_utc,
                country=country,
                currency=currency,
                region=region,
                title=title,
                category=category,
                description="",
                impact=impact,
                actual=actual,
                forecast=forecast,
                previous=previous,
                revised="",
                unit=_detect_unit(forecast or previous),
                raw=raw,
            )

        except Exception as exc:  # noqa: BLE001
            log.warning("ForexFactory: error parsing record %s — %s", raw, exc)
            return None

    def _filter_currencies(self, events: list[EconomicEvent]) -> list[EconomicEvent]:
        """Keep only events whose currency is in ``self.target_currencies``."""
        if not self.target_currencies:
            return events
        return [e for e in events if e.currency in self.target_currencies]


# ── Unit Detection Helper ─────────────────────────────────────


def _detect_unit(value: str) -> str:
    """
    Heuristically detect the unit of a value string.

    Examples
    --------
    >>> _detect_unit("59K")
    'K'
    >>> _detect_unit("-2.5%")
    '%'
    >>> _detect_unit("3.087")
    ''
    """
    if not value:
        return ""
    v = value.strip()
    if v.endswith("%"):
        return "%"
    if v.endswith("K"):
        return "K"
    if v.endswith("M"):
        return "M"
    if v.endswith("B"):
        return "B"
    if v.endswith("T"):
        return "T"
    return ""


# ── Standalone Execution ──────────────────────────────────────


def main() -> None:
    """
    Run the ForexFactory scraper as a standalone script.

    Output is printed to the terminal and also saved to the
    ``output/`` directory in both JSON and CSV formats.
    """
    import sys
    from utils.helpers import save_events, print_summary_table

    log.info("=" * 60)
    log.info("ForexFactory Economic Calendar Scraper")
    log.info("Target currencies : %s", config.FF_TARGET_CURRENCIES)
    log.info("=" * 60)

    scraper = ForexFactoryScraper()
    events = scraper.fetch()

    if not events:
        log.warning("No events to display.")
        sys.exit(0)

    # Print each event
    print()
    for e in events:
        print(e)

    # Summary
    print_summary_table(events, title="ForexFactory — USD Economic Calendar")

    # Save output
    save_events(
        events,
        output_dir=config.OUTPUT_DIR,
        filename_prefix="forexfactory_usd",
        fmt=config.OUTPUT_FORMAT,
    )


if __name__ == "__main__":
    main()
