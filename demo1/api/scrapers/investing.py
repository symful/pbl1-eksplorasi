import httpx
import re
import asyncio
import urllib.parse
from datetime import datetime, timezone
from typing import Optional

from tenacity import retry, stop_after_attempt, wait_exponential
from bs4 import BeautifulSoup

from api.models.schemas import EconomicEvent, ImpactLevel, Currency, Source


INVESTING_CALENDAR_URL = "https://www.investing.com/economic-calendar/"
INVESTING_CALENDAR_API = "https://www.investing.com/economic-calendar/Service/getCalendarFilteredData"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

COUNTRY_IDS = {
    "USD": 5,
    "IDR": 48,
}

IMPORTANCE_IDS = {
    "High": 1,
    "Medium": 2,
    "Low": 3,
}

FLAG_TO_CURRENCY = {
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

CURRENCY_COUNTRY_MAP = {
    "USD": ("US", "United States"),
    "IDR": ("ID", "Indonesia"),
    "EUR": ("EU", "Euro Area"),
    "GBP": ("GB", "United Kingdom"),
    "JPY": ("JP", "Japan"),
    "AUD": ("AU", "Australia"),
    "NZD": ("NZ", "New Zealand"),
    "CAD": ("CA", "Canada"),
    "CHF": ("CH", "Switzerland"),
    "CNY": ("CN", "China"),
    "KRW": ("KR", "South Korea"),
}

CATEGORY_KEYWORDS = {
    "rate decision": "Monetary Policy",
    "interest rate": "Monetary Policy",
    "fomc": "Monetary Policy",
    "fed": "Monetary Policy",
    "rapat": "Monetary Policy",
    "bi rate": "Monetary Policy",
    "cpi": "Inflation",
    "ppi": "Inflation",
    "inflation": "Inflation",
    "deflator": "Inflation",
    "ihk": "Inflation",
    "nonfarm": "Labour Market",
    "non-farm": "Labour Market",
    "payroll": "Labour Market",
    "unemployment": "Labour Market",
    "jobless": "Labour Market",
    "employment": "Labour Market",
    "adp": "Labour Market",
    "tenaga kerja": "Labour Market",
    "gdp": "Growth",
    "pdb": "Growth",
    "trade balance": "Trade",
    "neraca": "Trade",
    "export": "Trade",
    "import": "Trade",
    "pmi": "Business Activity",
    "ism": "Business Activity",
    "manufacturing": "Business Activity",
    "retail": "Consumer",
    "consumer confid": "Consumer",
}


def resolve_category(title: str) -> str:
    title_lower = title.lower()
    for keyword, category in CATEGORY_KEYWORDS.items():
        if keyword in title_lower:
            return category
    return ""


def clean_value(raw: str) -> str:
    if raw is None:
        return ""
    cleaned = str(raw).strip().replace("\xa0", "").replace("\u200b", "")
    if cleaned in ("-", "—", "N/A", "n/a", "na", "NA", "null", "None", ""):
        return ""
    return cleaned


def extract_currency(col) -> str:
    flag_span = col.find("span", class_=re.compile(r"ceFlags"))
    if flag_span:
        classes = flag_span.get("class", [])
        if classes:
            for cls in classes:
                if cls != "ceFlags" and len(cls) == 2:
                    currency = FLAG_TO_CURRENCY.get(cls.upper(), "")
                    if currency:
                        return currency

    text = clean_value(col.get_text()).upper()
    if len(text) == 3 and text.isalpha():
        return text
    return ""


def extract_impact(col) -> ImpactLevel:
    filled_count = 0
    for icon in col.find_all("i"):
        classes = " ".join(icon.get("class", []))
        if re.search(r"(bull|Bull|fullBull|FullBull)", classes):
            if "gray" not in classes.lower():
                filled_count += 1

    if filled_count >= 3:
        return ImpactLevel.HIGH
    if filled_count == 2:
        return ImpactLevel.MEDIUM
    return ImpactLevel.LOW


class InvestingScraper:
    def __init__(
        self,
        country_ids: dict[str, int] = None,
        importance_ids: dict[str, int] = None,
    ):
        self.country_ids = country_ids or COUNTRY_IDS
        self.importance_ids = importance_ids or IMPORTANCE_IDS
        self._client: Optional[httpx.AsyncClient] = None
        self._session_initialized = False

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "X-Requested-With": "XMLHttpRequest",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Referer": INVESTING_CALENDAR_URL,
                    "Origin": "https://www.investing.com",
                },
                timeout=30.0,
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _init_session(self, client: httpx.AsyncClient):
        if self._session_initialized:
            return

        try:
            await client.get(INVESTING_CALENDAR_URL)
            self._session_initialized = True
        except Exception:
            pass

        await asyncio.sleep(1)

    def _build_post_body(
        self, date_from: str, date_to: str, limit_from: int = 0
    ) -> list[tuple[str, str]]:
        body = []
        for val in self.country_ids.values():
            body.append(("country[]", str(val)))
        for val in self.importance_ids.values():
            body.append(("importance[]", str(val)))
        body.append(("dateFrom", date_from))
        body.append(("dateTo", date_to))
        body.append(("currentTab", "custom"))
        body.append(("submitFilters", "1"))
        body.append(("limit_from", str(limit_from)))
        return body

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _request_calendar_data(
        self, client: httpx.AsyncClient, date_from: str, date_to: str, limit_from: int = 0
    ) -> Optional[str]:
        body = self._build_post_body(date_from, date_to, limit_from)

        try:
            response = await client.post(
                INVESTING_CALENDAR_API,
                content=urllib.parse.urlencode(body).encode(),
            )
            response.raise_for_status()
            payload = response.json()
            return payload.get("data", "")
        except Exception:
            raise

    def _parse_date_header(self, row) -> Optional[str]:
        td = row.find("td")
        if td:
            td_id = td.get("id", "")
            match = re.search(r"theDay_(\d{9,11})", str(td_id))
            if match:
                try:
                    ts = int(match.group(1))
                    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                    return dt.strftime("%Y-%m-%d")
                except (ValueError, OSError):
                    pass

        text = row.get_text(separator=" ", strip=True)
        date_patterns = [
            r"\b(\w+,\s+\w+\s+\d{1,2},\s+\d{4})\b",
            r"\b(\w+\s+\d{1,2},\s+\d{4})\b",
        ]
        for pattern in date_patterns:
            m = re.search(pattern, text)
            if m:
                raw_date = m.group(1)
                for fmt in ("%A, %B %d, %Y", "%B %d, %Y"):
                    try:
                        return datetime.strptime(raw_date, fmt).strftime("%Y-%m-%d")
                    except ValueError:
                        continue
        return None

    def _parse_event_row(self, row, current_date: str) -> Optional[EconomicEvent]:
        try:
            cols = row.find_all("td")
            if len(cols) < 4:
                return None

            event_id = str(row.get("event_attr_id", "") or row.get("id", ""))

            time_str = clean_value(cols[0].get_text())
            if time_str.lower() in ("all day", "tentative", ""):
                time_str = ""

            currency_code = extract_currency(cols[1])
            if not currency_code or currency_code not in CURRENCY_COUNTRY_MAP:
                return None

            impact = extract_impact(cols[2])

            title_col = cols[3]
            a_tag = title_col.find("a")
            title = clean_value(a_tag.get_text() if a_tag else title_col.get_text())
            if not title:
                return None

            actual = clean_value(cols[4].get_text()) if len(cols) > 4 else ""
            forecast = clean_value(cols[5].get_text()) if len(cols) > 5 else ""
            previous = clean_value(cols[6].get_text()) if len(cols) > 6 else ""

            country, region = CURRENCY_COUNTRY_MAP.get(currency_code, ("", ""))

            datetime_utc = None
            if current_date and time_str:
                try:
                    dt = datetime.strptime(f"{current_date} {time_str}", "%Y-%m-%d %H:%M")
                    datetime_utc = dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    pass

            return EconomicEvent(
                source=Source.INVESTING,
                event_id=event_id,
                date=current_date,
                time=time_str,
                datetime_utc=datetime_utc,
                country=country,
                currency=Currency(currency_code),
                region=region,
                title=title,
                category=resolve_category(title),
                description="",
                impact=impact,
                actual=actual,
                forecast=forecast,
                previous=previous,
                revised="",
                unit="",
                sentiment="",
            )
        except Exception:
            return None

    async def fetch(
        self,
        date_from: str,
        date_to: str,
        impact_filter: list[str] = None,
    ) -> list[EconomicEvent]:
        client = await self._get_client()
        await self._init_session(client)

        all_events = []
        offset = 0
        page = 0
        seen_keys = set()

        while True:
            page += 1
            await asyncio.sleep(2)

            html_fragment = await self._request_calendar_data(
                client, date_from, date_to, limit_from=offset
            )
            if not html_fragment:
                break

            soup = BeautifulSoup(html_fragment, "html.parser")
            current_date = date_from
            events = []

            for row in soup.find_all("tr"):
                row_classes = row.get("class", [])

                if row_classes:
                    if "theDay" in row_classes or "js-calendar-header" in row_classes:
                        parsed = self._parse_date_header(row)
                        if parsed:
                            current_date = parsed
                        continue

                    if "js-event-item" in row_classes or row.get("event_attr_id"):
                        event = self._parse_event_row(row, current_date)
                        if event:
                            events.append(event)

            if not events:
                break

            new_count = 0
            for e in events:
                key = f"{e.date}|{e.time}|{e.currency}|{e.title}"
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                if impact_filter is None or e.impact.value in impact_filter:
                    all_events.append(e)
                    new_count += 1

            if new_count == 0:
                break

            offset += len(events)
            if page >= 50:
                break

        return sorted(all_events, key=lambda e: (e.date, e.time or "00:00"))


async def fetch_investing_events(
    date_from: str,
    date_to: str,
    currencies: list[str] = None,
    impact_filter: list[str] = None,
) -> list[EconomicEvent]:
    country_ids = {c: COUNTRY_IDS[c] for c in (currencies or ["USD", "IDR"]) if c in COUNTRY_IDS}

    scraper = InvestingScraper(country_ids=country_ids)
    try:
        events = await scraper.fetch(
            date_from=date_from,
            date_to=date_to,
            impact_filter=impact_filter,
        )
        return events
    finally:
        await scraper.close()
