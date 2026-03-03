# ============================================================
# Economic Calendar Scraper - Investing.com
# ============================================================
#
# Data Source : https://www.investing.com/economic-calendar/
# Internal API: POST /economic-calendar/Service/getCalendarFilteredData
# Coverage    : USD (United States) + IDR (Indonesia)
# Auth        : None — but requires proper browser-like headers
#               and a valid session cookie (fetched automatically).
#
# Investing.com renders their economic calendar via an internal
# AJAX endpoint. This scraper:
#
#   1. GETs the calendar page to establish a session cookie
#   2. POSTs to the internal API with country/importance filters
#   3. Receives a JSON payload whose "data" key contains an
#      HTML fragment of <tr> rows
#   4. Parses those rows with BeautifulSoup
#
# Investing.com country IDs (used in the POST body):
#   5  → United States (USD)
#   48 → Indonesia     (IDR)
#
# Importance IDs:
#   1 → High
#   2 → Medium
#   3 → Low
# ============================================================

from __future__ import annotations

import re
import sys
import os
import time
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup, Tag

# Allow running this file directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
from models.economic_event import EconomicEvent
from utils.helpers import (
    TZ_WIB,
    build_session,
    clean_value,
    currency_to_country,
    currency_to_region,
    format_display_datetime,
    get_logger,
    get_scrape_window,
    resolve_category,
    safe_get,
    safe_post,
    sort_events,
)

log = get_logger("investing", config.LOG_LEVEL)

SOURCE_NAME = "investing"

# ── Impact parsing ────────────────────────────────────────────
# Investing.com encodes importance via CSS class names on the <td> element
# ("bull" icons) or via a <span> wrapping a number of filled icons.
# We count the "grayFullBullishIcon" (or "bullish") icons to derive impact.
_ICON_TO_IMPACT: dict[int, str] = {
    3: "High",
    2: "Medium",
    1: "Low",
    0: "Low",
}

# Map the country flag CSS class to a currency code.
# Investing.com places classes like "ceFlags US" or "ceFlags ID" on spans.
_FLAG_TO_CURRENCY: dict[str, str] = {
    "US": "USD",
    "ID": "IDR",
    "EU": "EUR",
    "GB": "GBP",
    "JP": "JPY",
    "AU": "AUD",
    "NZ": "NZD",
    "CA": "CAD",
    "CH": "CHF",
    "CN": "CNY",
    "KR": "KRW",
}

# Fallback: text inside the currency cell → currency code
_TEXT_TO_CURRENCY: dict[str, str] = {
    "usd": "USD",
    "idr": "IDR",
    "eur": "EUR",
    "gbp": "GBP",
    "jpy": "JPY",
    "aud": "AUD",
    "nzd": "NZD",
    "cad": "CAD",
    "chf": "CHF",
    "cny": "CNY",
    "krw": "KRW",
}


# ── Scraper Class ─────────────────────────────────────────────


class InvestingComScraper:
    """
    Scrapes the Investing.com economic calendar for USD and IDR events.

    The scraper fetches a date window (``days_back`` .. ``days_ahead``)
    relative to today, normalises each row into an ``EconomicEvent``,
    and optionally filters by impact level.

    Usage
    -----
    >>> scraper = InvestingComScraper()
    >>> events = scraper.fetch()
    >>> for event in events:
    ...     print(event)
    """

    def __init__(
        self,
        country_ids: Optional[dict[str, int]] = None,
        importance_ids: Optional[dict[str, int]] = None,
        impact_filter: Optional[list[str]] = None,
        days_back: int = config.DAYS_BACK,
        days_ahead: int = config.DAYS_AHEAD,
    ) -> None:
        """
        Parameters
        ----------
        country_ids:
            Dict mapping currency code → Investing.com country ID.
            Defaults to ``config.INVESTING_COUNTRY_IDS``.
        importance_ids:
            Dict mapping impact label → Investing.com importance ID.
            Defaults to ``config.INVESTING_IMPORTANCE_IDS``.
        impact_filter:
            Optional list of impact levels to keep after parsing.
            ``None`` keeps all levels.
        days_back:
            How many days before today to include.
        days_ahead:
            How many days after today to include.
        """
        self.country_ids: dict[str, int] = country_ids or config.INVESTING_COUNTRY_IDS
        self.importance_ids: dict[str, int] = (
            importance_ids or config.INVESTING_IMPORTANCE_IDS
        )
        self.impact_filter: Optional[list[str]] = impact_filter
        self.days_back = days_back
        self.days_ahead = days_ahead

        self._session = build_session(
            headers=config.INVESTING_HEADERS,
            retries=config.MAX_RETRIES,
            proxies=config.PROXIES,
        )
        self._session_initialised = False

    # ── Public API ────────────────────────────────────────────

    def fetch(self) -> list[EconomicEvent]:
        """
        Fetch and return economic events from Investing.com.

        Automatically initialises a browser-like session (including
        cookies) before making the data request.

        Returns
        -------
        Sorted list of ``EconomicEvent`` objects.
        """
        self._init_session()

        date_from, date_to = get_scrape_window(
            days_back=self.days_back,
            days_ahead=self.days_ahead,
            tz=TZ_WIB,
        )
        log.info(
            "📡 Fetching Investing.com calendar (%s → %s) for %s…",
            date_from,
            date_to,
            list(self.country_ids.keys()),
        )

        html_fragment = self._request_calendar_data(date_from, date_to)
        if not html_fragment:
            log.error("Investing.com: received empty data from API.")
            return []

        events = self._parse_html_fragment(html_fragment, date_from)
        log.info("Investing.com: parsed %d raw events.", len(events))

        if self.impact_filter:
            events = [e for e in events if e.impact in self.impact_filter]
            log.info(
                "Investing.com: %d events after impact filter %s",
                len(events),
                self.impact_filter,
            )

        return sort_events(events)

    def fetch_high_impact(self) -> list[EconomicEvent]:
        """Convenience method — returns only High-impact events."""
        return [e for e in self.fetch() if e.impact == "High"]

    # ── Session Initialisation ────────────────────────────────

    def _init_session(self) -> None:
        """
        Perform a GET request to the Investing.com calendar page to
        obtain session cookies and confirm connectivity.

        This mirrors what a real browser does before the AJAX call.
        Called automatically by ``fetch()``.
        """
        if self._session_initialised:
            return

        log.debug("Initialising Investing.com session…")
        resp = safe_get(
            self._session,
            config.INVESTING_CALENDAR_URL,
            timeout=config.REQUEST_TIMEOUT,
            delay=config.REQUEST_DELAY,
            logger=log,
        )
        if resp is None:
            log.warning(
                "Could not load Investing.com calendar page. "
                "Proceeding without session cookies — requests may be blocked."
            )
        else:
            log.debug(
                "Session initialised. Cookies: %s",
                dict(self._session.cookies),
            )
            self._session_initialised = True

        # Small pause to be polite
        time.sleep(1)

    # ── API Request ───────────────────────────────────────────

    def _build_post_body(self, date_from: str, date_to: str) -> dict:
        """
        Build the form-encoded POST body for the Investing.com
        internal calendar API.

        The body must list each country ID and importance ID separately
        using repeated keys with the ``[]`` suffix (PHP-style arrays).
        """
        # requests encodes list values as repeated keys when a list is used
        body: dict = {
            "dateFrom": date_from,
            "dateTo": date_to,
            "currentTab": "custom",
            "submitFilters": "1",
            "limit_from": "0",
        }

        # Add country IDs as repeated keys: country[]=5&country[]=48
        # requests.post(data=...) handles lists for the same key correctly.
        country_values = list(self.country_ids.values())
        importance_values = list(self.importance_ids.values())

        # We use a list of tuples to preserve repeated keys
        body_tuples: list[tuple[str, str]] = []
        for val in country_values:
            body_tuples.append(("country[]", str(val)))
        for val in importance_values:
            body_tuples.append(("importance[]", str(val)))
        body_tuples.append(("dateFrom", date_from))
        body_tuples.append(("dateTo", date_to))
        body_tuples.append(("currentTab", "custom"))
        body_tuples.append(("submitFilters", "1"))
        body_tuples.append(("limit_from", "0"))

        return body_tuples  # type: ignore[return-value]

    def _request_calendar_data(self, date_from: str, date_to: str) -> Optional[str]:
        """
        POST to the Investing.com internal API and return the raw HTML
        fragment from the ``data`` key, or ``None`` on failure.
        """
        body = self._build_post_body(date_from, date_to)

        resp = safe_post(
            self._session,
            config.INVESTING_CALENDAR_API,
            data=body,
            timeout=config.REQUEST_TIMEOUT,
            delay=config.REQUEST_DELAY,
            logger=log,
        )

        if resp is None:
            return None

        # The response is a JSON envelope with an HTML "data" key.
        try:
            payload = resp.json()
        except ValueError:
            log.warning(
                "Investing.com: response is not JSON. "
                "Site may be blocking the request. Status: %d",
                resp.status_code,
            )
            log.debug("Response text (first 500 chars): %s", resp.text[:500])
            return None

        html = payload.get("data", "")
        if not html:
            log.warning(
                "Investing.com: JSON response has no 'data' key or it is empty. "
                "Payload keys: %s",
                list(payload.keys()),
            )
            return None

        rows_num = payload.get("rows_num", "unknown")
        log.debug("Investing.com: API returned ~%s rows.", rows_num)
        return html

    # ── HTML Parsing ──────────────────────────────────────────

    def _parse_html_fragment(
        self, html: str, fallback_date: str
    ) -> list[EconomicEvent]:
        """
        Parse the HTML fragment returned by the Investing.com API.

        The fragment contains a series of:
        * ``<tr class="theDay">`` date separator rows
        * ``<tr class="js-event-item">`` event data rows

        Each event row has columns:
            [0] time
            [1] currency flag
            [2] importance (bull icons)
            [3] event title
            [4] actual
            [5] forecast
            [6] previous
            [7] (optional graph icon)

        Parameters
        ----------
        html:
            Raw HTML string from the API response's ``data`` key.
        fallback_date:
            Date string (YYYY-MM-DD) to use when the date header is
            not found before the first event row.
        """
        soup = BeautifulSoup(html, "lxml")
        events: list[EconomicEvent] = []
        current_date = fallback_date

        for row in soup.find_all("tr"):
            row_classes = row.get("class", [])

            if row_classes:
                # ── Date separator row ──────────────────────────
                if "theDay" in row_classes or "js-calendar-header" in row_classes:
                    parsed = self._parse_date_header(row)
                    if parsed:
                        current_date = parsed
                    continue

                # ── Event data row ──────────────────────────────
                if "js-event-item" in row_classes or row.get("event_attr_id"):
                    event = self._parse_event_row(row, current_date)
                    if event is not None:
                        events.append(event)

        return events

    def _parse_date_header(self, row: Tag) -> Optional[str]:
        """
        Extract a date string (YYYY-MM-DD) from a date-header <tr>.

        Investing.com date headers look like:
            <tr class="theDay">
              <td colspan="..." id="...">
                <span>Tuesday, March 4, 2025</span>
              </td>
            </tr>

        The ``id`` attribute on the <td> often encodes the date as an
        epoch timestamp which is more reliable than the text.
        """
        # Try the <td> id attribute first (epoch seconds)
        td = row.find("td")
        if td:
            td_id = td.get("id", "")
            # Typical pattern: "theDay_1741132800"
            match = re.search(r"theDay_(\d{9,11})", str(td_id))
            if match:
                try:
                    ts = int(match.group(1))
                    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                    return dt.strftime("%Y-%m-%d")
                except (ValueError, OSError):
                    pass

        # Fallback: parse the visible text
        text = row.get_text(separator=" ", strip=True)
        # Common format: "Tuesday, March 4, 2025"
        date_patterns = [
            r"\b(\w+,\s+\w+\s+\d{1,2},\s+\d{4})\b",  # "Tuesday, March 4, 2025"
            r"\b(\w+\s+\d{1,2},\s+\d{4})\b",  # "March 4, 2025"
            r"\b(\d{4}-\d{2}-\d{2})\b",  # "2025-03-04" (rare)
        ]
        for pattern in date_patterns:
            m = re.search(pattern, text)
            if m:
                raw_date = m.group(1)
                for fmt in (
                    "%A, %B %d, %Y",
                    "%B %d, %Y",
                    "%Y-%m-%d",
                ):
                    try:
                        return datetime.strptime(raw_date, fmt).strftime("%Y-%m-%d")
                    except ValueError:
                        continue

        return None

    def _parse_event_row(self, row: Tag, current_date: str) -> Optional[EconomicEvent]:
        """
        Convert a single ``<tr class="js-event-item">`` into an
        ``EconomicEvent`` object.
        """
        try:
            cols = row.find_all("td")
            if len(cols) < 4:
                return None

            event_id = str(row.get("event_attr_id", "") or row.get("id", ""))

            # ── Time ────────────────────────────────────────
            time_str = clean_value(cols[0].get_text())
            # Normalize "All Day" / "Tentative" placeholders
            if time_str.lower() in ("all day", "tentative", ""):
                time_str = ""

            # ── Currency ────────────────────────────────────
            currency = self._extract_currency(cols[1])
            if not currency:
                return None  # Skip rows without a currency

            # ── Importance ──────────────────────────────────
            impact = self._extract_impact(cols[2])

            # ── Event Title ─────────────────────────────────
            title_col = cols[3]
            # The title is sometimes inside an <a> tag
            a_tag = title_col.find("a")
            title = clean_value(a_tag.get_text() if a_tag else title_col.get_text())
            if not title:
                return None

            # ── Values ──────────────────────────────────────
            actual = clean_value(cols[4].get_text()) if len(cols) > 4 else ""
            forecast = clean_value(cols[5].get_text()) if len(cols) > 5 else ""
            previous = clean_value(cols[6].get_text()) if len(cols) > 6 else ""

            # Build UTC datetime for sorting (approximate — time is local)
            datetime_utc = self._build_utc_datetime(current_date, time_str, currency)

            category = resolve_category(title, config.EVENT_CATEGORIES)
            country = currency_to_country(currency)
            region = currency_to_region(currency)

            return EconomicEvent(
                source=SOURCE_NAME,
                event_id=event_id,
                date=current_date,
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
                unit="",
                raw={
                    "event_id": event_id,
                    "date": current_date,
                    "time": time_str,
                    "currency": currency,
                    "impact": impact,
                    "title": title,
                    "actual": actual,
                    "forecast": forecast,
                    "previous": previous,
                },
            )

        except Exception as exc:  # noqa: BLE001
            log.warning(
                "Investing.com: error parsing event row — %s\nRow HTML: %s",
                exc,
                str(row)[:300],
            )
            return None

    # ── Cell Extractors ───────────────────────────────────────

    def _extract_currency(self, col: Tag) -> str:
        """
        Extract the currency code from the flag cell.

        The flag cell contains a ``<span class="ceFlags XX">`` where XX
        is the ISO-2 country code.  The text content is the currency code.
        """
        # Try flag span class first
        flag_span = col.find("span", class_=re.compile(r"ceFlags"))
        if flag_span:
            classes = flag_span.get("class", [])
            if classes:
                for cls in classes:
                    if cls != "ceFlags" and len(cls) == 2:
                        currency = _FLAG_TO_CURRENCY.get(cls.upper(), "")
                        if currency:
                            return currency

        # Fallback: plain text of the cell
        text = clean_value(col.get_text()).upper()
        if text in _TEXT_TO_CURRENCY:
            return _TEXT_TO_CURRENCY[text]
        if len(text) == 3 and text.isalpha():
            return text

        return ""

    def _extract_impact(self, col: Tag) -> str:
        """
        Extract the impact level from the importance/sentiment cell.

        Investing.com uses filled bull icons to indicate importance:
        * 3 filled icons → High
        * 2 filled icons → Medium
        * 1 filled icon  → Low

        The icons are ``<i>`` elements with class names containing
        "bullish" or "FullBullishIcon".  Gray (unfilled) icons are
        ignored.
        """
        # Count filled (non-gray) bullish icons
        filled_count = 0
        for icon in col.find_all("i"):
            classes = " ".join(icon.get("class", []))
            # "grayFullBullishIcon" = filled but gray (represents the total slots)
            # We look for positively-classed icons
            if re.search(r"(bull|Bull|fullBull|FullBull)", classes):
                if "gray" not in classes.lower():
                    filled_count += 1

        if filled_count >= 3:
            return "High"
        if filled_count == 2:
            return "Medium"
        if filled_count == 1:
            return "Low"

        # Alternative: some versions use a <span class="bull"> wrapper
        # with a numeric text content or a title attribute
        span = col.find("span", class_=re.compile(r"bull|sentiment"))
        if span:
            title_attr = span.get("title", "").lower()
            if "high" in title_attr:
                return "High"
            if "medium" in title_attr or "moderate" in title_attr:
                return "Medium"
            if "low" in title_attr:
                return "Low"

        return "Low"

    # ── UTC Datetime Builder ──────────────────────────────────

    def _build_utc_datetime(
        self,
        date_str: str,
        time_str: str,
        currency: str,
    ) -> Optional[datetime]:
        """
        Construct an approximate UTC datetime from a local date + time.

        Investing.com displays times in the user's configured timezone.
        We assume ET (New York) for USD events and WIB (Jakarta) for IDR.
        """
        if not date_str or not time_str:
            return None

        tz_map: dict[str, ZoneInfo] = {
            "USD": ZoneInfo("America/New_York"),
            "IDR": ZoneInfo("Asia/Jakarta"),
        }
        local_tz = tz_map.get(currency, ZoneInfo("UTC"))

        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %I:%M%p", "%Y-%m-%d %I:%M %p"):
            try:
                dt_local = datetime.strptime(f"{date_str} {time_str}", fmt).replace(
                    tzinfo=local_tz
                )
                return dt_local.astimezone(timezone.utc)
            except ValueError:
                continue

        return None


# ── Standalone Execution ──────────────────────────────────────


def main() -> None:
    """
    Run the Investing.com scraper as a standalone script.

    Output is printed to the terminal and also saved to the
    ``output/`` directory in both JSON and CSV formats.
    """
    from utils.helpers import save_events, print_summary_table

    log.info("=" * 60)
    log.info("Investing.com Economic Calendar Scraper")
    log.info("Target countries : %s", list(config.INVESTING_COUNTRY_IDS.keys()))
    log.info("=" * 60)

    scraper = InvestingComScraper()
    events = scraper.fetch()

    if not events:
        log.warning("No events to display.")
        return

    print()
    for e in events:
        print(e)

    print_summary_table(events, title="Investing.com — USD + IDR Economic Calendar")

    # Save USD and IDR separately for convenience
    usd_events = [e for e in events if e.currency == "USD"]
    idr_events = [e for e in events if e.currency == "IDR"]

    if usd_events:
        save_events(
            usd_events,
            output_dir=config.OUTPUT_DIR,
            filename_prefix="investing_usd",
            fmt=config.OUTPUT_FORMAT,
        )
    if idr_events:
        save_events(
            idr_events,
            output_dir=config.OUTPUT_DIR,
            filename_prefix="investing_idr",
            fmt=config.OUTPUT_FORMAT,
        )

    # Save combined
    save_events(
        events,
        output_dir=config.OUTPUT_DIR,
        filename_prefix="investing_all",
        fmt=config.OUTPUT_FORMAT,
    )


if __name__ == "__main__":
    main()
