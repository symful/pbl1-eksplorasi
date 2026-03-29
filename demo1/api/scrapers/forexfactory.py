import httpx
from datetime import datetime, timezone
from typing import Optional
import asyncio

from tenacity import retry, stop_after_attempt, wait_exponential

from api.models.schemas import EconomicEvent, ImpactLevel, Currency, Source


FF_BASE_URL = "https://nfs.faireconomy.media"
FF_THIS_WEEK = f"{FF_BASE_URL}/ff_calendar_thisweek.json"
FF_NEXT_WEEK = f"{FF_BASE_URL}/ff_calendar_nextweek.json"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

IMPACT_MAP = {
    "High": ImpactLevel.HIGH,
    "Medium": ImpactLevel.MEDIUM,
    "Low": ImpactLevel.LOW,
    "Holiday": ImpactLevel.LOW,
    "": ImpactLevel.LOW,
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
    "cpi": "Inflation",
    "ppi": "Inflation",
    "inflation": "Inflation",
    "nonfarm": "Labour Market",
    "non-farm": "Labour Market",
    "payroll": "Labour Market",
    "unemployment": "Labour Market",
    "gdp": "Growth",
    "trade balance": "Trade",
    "pmi": "Business Activity",
    "ism": "Business Activity",
    "retail": "Consumer",
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


def parse_ff_datetime(iso_str: str) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def detect_unit(value: str) -> str:
    if not value:
        return ""
    v = value.strip()
    if v.endswith("%"):
        return "%"
    if v.endswith(("K", "M", "B", "T")):
        return v[-1]
    return ""


class ForexFactoryScraper:
    def __init__(self, target_currencies: list[str] = None):
        self.target_currencies = [c.upper() for c in (target_currencies or ["USD"])]
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": USER_AGENT},
                timeout=30.0,
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _fetch_url(self, client: httpx.AsyncClient, url: str) -> Optional[list[dict]]:
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
        except Exception:
            raise

    async def fetch(self, impact_filter: list[str] = None) -> list[EconomicEvent]:
        client = await self._get_client()
        all_events = []

        for label, url in [("this_week", FF_THIS_WEEK), ("next_week", FF_NEXT_WEEK)]:
            data = await self._fetch_url(client, url)
            if data is None:
                continue

            for raw in data:
                event = self._parse_record(raw)
                if event and event.currency in self.target_currencies:
                    if impact_filter is None or event.impact.value in impact_filter:
                        all_events.append(event)

        return sorted(all_events, key=lambda e: (e.date, e.time or "00:00"))

    def _parse_record(self, raw: dict) -> Optional[EconomicEvent]:
        try:
            currency = clean_value(raw.get("country", "")).upper()
            title = clean_value(raw.get("title", ""))
            impact_raw = clean_value(raw.get("impact", ""))
            date_iso = clean_value(raw.get("date", ""))
            forecast = clean_value(raw.get("forecast", ""))
            previous = clean_value(raw.get("previous", ""))
            actual = clean_value(raw.get("actual", ""))

            if not title or not date_iso:
                return None

            if currency not in CURRENCY_COUNTRY_MAP:
                return None

            country, region = CURRENCY_COUNTRY_MAP.get(currency, ("", ""))
            impact = IMPACT_MAP.get(impact_raw, ImpactLevel.LOW)

            datetime_utc = parse_ff_datetime(date_iso)
            if datetime_utc:
                date_str = datetime_utc.strftime("%Y-%m-%d")
                time_str = datetime_utc.strftime("%H:%M")
            else:
                date_str = date_iso[:10] if len(date_iso) >= 10 else date_iso
                time_str = ""

            return EconomicEvent(
                source=Source.FOREXFACTORY,
                event_id="",
                date=date_str,
                time=time_str,
                datetime_utc=datetime_utc,
                country=country,
                currency=Currency(currency),
                region=region,
                title=title,
                category=resolve_category(title),
                description="",
                impact=impact,
                actual=actual,
                forecast=forecast,
                previous=previous,
                revised="",
                unit=detect_unit(forecast or previous),
                sentiment="",
            )
        except Exception:
            return None


async def fetch_forexfactory_events(
    currencies: list[str] = None,
    impact_filter: list[str] = None,
) -> list[EconomicEvent]:
    scraper = ForexFactoryScraper(target_currencies=currencies or ["USD"])
    try:
        events = await scraper.fetch(impact_filter=impact_filter)
        return events
    finally:
        await scraper.close()
