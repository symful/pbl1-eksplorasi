from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ImpactLevel(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class Currency(str, Enum):
    USD = "USD"
    IDR = "IDR"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"
    AUD = "AUD"
    CNY = "CNY"


class Source(str, Enum):
    FOREXFACTORY = "forexfactory"
    INVESTING = "investing"
    YAHOO = "yfinance"


class EconomicEvent(BaseModel):
    source: Source
    event_id: str = ""
    date: str
    time: str = ""
    datetime_utc: Optional[datetime] = None
    country: str
    currency: Currency
    region: str
    title: str
    category: str = ""
    description: str = ""
    impact: ImpactLevel
    actual: str = ""
    forecast: str = ""
    previous: str = ""
    revised: str = ""
    unit: str = ""
    sentiment: str = ""

    class Config:
        use_enum_values = True


class EconomicCalendarResponse(BaseModel):
    events: list[EconomicEvent]
    total_count: int
    usd_count: int
    idr_count: int
    high_impact_count: int
    sources: list[str]
    fetched_at: datetime
    date_from: str
    date_to: str
    errors: Optional[list[str]] = None


class PriceBar(BaseModel):
    ticker: str
    symbol: str
    interval: str
    datetime_utc: str
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    adj_close: Optional[float] = None
    volume: Optional[float] = None


class QuoteSnapshot(BaseModel):
    ticker: str
    symbol: str
    fetched_at_utc: str
    currency: Optional[str] = None
    exchange: Optional[str] = None
    quote_type: Optional[str] = None
    last_price: Optional[float] = None
    previous_close: Optional[float] = None
    open: Optional[float] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    market_time_utc: Optional[str] = None


class PriceHistoryResponse(BaseModel):
    symbol: str
    ticker: str
    interval: str
    period: str
    bars: list[PriceBar]
    bar_count: int
    fetched_at: datetime


class QuoteResponse(BaseModel):
    quote: QuoteSnapshot
    fetched_at: datetime


class MarketOverviewItem(BaseModel):
    ticker: str
    symbol: str
    name: str
    country: str
    last_price: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    previous_close: Optional[float] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    volume: Optional[float] = None
    error: Optional[str] = None


class MarketOverviewResponse(BaseModel):
    country: str
    items: list[MarketOverviewItem]
    fetched_at: datetime
    errors: Optional[list[str]] = None
