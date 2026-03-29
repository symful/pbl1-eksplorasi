# ============================================================
# Economic Calendar Scraper - Data Model
# ============================================================

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class EconomicEvent:
    """
    Represents a single economic calendar event.

    This is the canonical data model used across all scrapers.
    Every scraper normalises its raw output into this structure
    before the data is merged, filtered, or exported.
    """

    # ── Identity ────────────────────────────────────────────
    source: str
    """Which scraper produced this event (e.g. 'forexfactory', 'investing', 'bi', 'bps')."""

    event_id: str = ""
    """Optional source-specific unique ID (e.g. Investing.com's event_attr_id)."""

    # ── Time ────────────────────────────────────────────────
    date: str = ""
    """ISO-8601 date string: YYYY-MM-DD."""

    time: str = ""
    """Local time of the event: HH:MM or 'All Day' / 'Tentative'."""

    datetime_utc: Optional[datetime] = None
    """Parsed UTC datetime object; None when the exact time is unknown."""

    # ── Location / Currency ─────────────────────────────────
    country: str = ""
    """ISO-2 country code, e.g. 'US', 'ID'."""

    currency: str = ""
    """3-letter ISO-4217 currency code, e.g. 'USD', 'IDR'."""

    region: str = ""
    """Human-readable region label, e.g. 'United States', 'Indonesia'."""

    # ── Event Details ────────────────────────────────────────
    title: str = ""
    """Full event title, e.g. 'Non-Farm Employment Change'."""

    category: str = ""
    """Semantic category assigned from config.EVENT_CATEGORIES, e.g. 'Labour Market'."""

    description: str = ""
    """Optional longer description of the event (used when available)."""

    # ── Market Impact ────────────────────────────────────────
    impact: str = ""
    """Expected market impact: 'High', 'Medium', or 'Low'."""

    impact_emoji: str = field(init=False)
    """Emoji shorthand for quick terminal display."""

    # ── Data Values ─────────────────────────────────────────
    actual: str = ""
    """Released actual value; empty string when not yet published."""

    forecast: str = ""
    """Analyst consensus / forecast value."""

    previous: str = ""
    """Previously published value (sometimes revised)."""

    revised: str = ""
    """Revised previous value when an amendment has been published."""

    unit: str = ""
    """Unit of measurement, e.g. '%', 'K', 'B', 'M' (populated when detectable)."""

    # ── Sentiment ───────────────────────────────────────────
    sentiment: str = ""
    """
    Relative outcome vs forecast: 'better', 'worse', 'as_expected', or ''.
    Populated automatically via resolve_sentiment().
    """

    # ── Raw ─────────────────────────────────────────────────
    raw: dict = field(default_factory=dict)
    """
    The original raw data dict from the source, preserved for debugging.
    Excluded from CSV exports to keep files clean.
    """

    # ────────────────────────────────────────────────────────
    def __post_init__(self) -> None:
        self.impact_emoji = self._impact_to_emoji(self.impact)
        if not self.sentiment and self.actual and self.forecast:
            self.sentiment = self.resolve_sentiment()

    # ── Helpers ─────────────────────────────────────────────
    @staticmethod
    def _impact_to_emoji(impact: str) -> str:
        return {
            "High": "🔴",
            "Medium": "🟡",
            "Low": "⚪",
        }.get(impact, "❔")

    def resolve_sentiment(self) -> str:
        """
        Compare actual vs forecast to derive a simple sentiment label.

        Returns 'better', 'worse', 'as_expected', or '' when values
        cannot be parsed as numbers.
        """
        try:
            actual_val = _parse_numeric(self.actual)
            forecast_val = _parse_numeric(self.forecast)
        except (ValueError, TypeError):
            return ""

        if actual_val is None or forecast_val is None:
            return ""

        diff = abs(actual_val - forecast_val)
        # Treat values within 0.5 % of the forecast as "as expected"
        tolerance = abs(forecast_val) * 0.005 if forecast_val != 0 else 0.001

        if diff <= tolerance:
            return "as_expected"
        return "better" if actual_val > forecast_val else "worse"

    @property
    def is_released(self) -> bool:
        """True when the actual value has been published."""
        return bool(self.actual and self.actual not in ("-", "—", "N/A", ""))

    @property
    def is_high_impact(self) -> bool:
        return self.impact == "High"

    @property
    def display_time(self) -> str:
        """Human-friendly date + time string."""
        if self.time:
            return f"{self.date} {self.time}"
        return self.date

    # ── Serialisation ────────────────────────────────────────
    def to_dict(self, include_raw: bool = False) -> dict:
        """Return a plain dict, optionally excluding the 'raw' field."""
        d = asdict(self)
        if not include_raw:
            d.pop("raw", None)
        # datetime objects are not JSON serialisable by default
        if isinstance(d.get("datetime_utc"), datetime):
            d["datetime_utc"] = d["datetime_utc"].isoformat()
        return d

    def to_json(self, include_raw: bool = False, indent: int = 2) -> str:
        return json.dumps(
            self.to_dict(include_raw=include_raw), ensure_ascii=False, indent=indent
        )

    # ── Factory helpers ──────────────────────────────────────
    @classmethod
    def from_dict(cls, data: dict) -> "EconomicEvent":
        """
        Reconstruct an EconomicEvent from a plain dict.
        Extra / unknown keys are silently ignored for forward compatibility.
        """
        known_fields = cls.__dataclass_fields__.keys()  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known_fields}
        # Re-parse datetime_utc if it was stored as an ISO string
        raw_dt = filtered.get("datetime_utc")
        if isinstance(raw_dt, str) and raw_dt:
            try:
                filtered["datetime_utc"] = datetime.fromisoformat(raw_dt)
            except ValueError:
                filtered["datetime_utc"] = None
        return cls(**filtered)

    # ── Display ──────────────────────────────────────────────
    def __str__(self) -> str:
        released = f" → Actual: {self.actual}" if self.is_released else ""
        forecast = f" | Forecast: {self.forecast}" if self.forecast else ""
        prev = f" | Prev: {self.previous}" if self.previous else ""
        return (
            f"[{self.impact_emoji} {self.impact:6}] "
            f"{self.display_time} | {self.currency} | "
            f"{self.title}{released}{forecast}{prev}"
        )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"EconomicEvent(source={self.source!r}, date={self.date!r}, "
            f"currency={self.currency!r}, title={self.title!r}, "
            f"impact={self.impact!r})"
        )


# ── Utility ──────────────────────────────────────────────────


def _parse_numeric(value: str) -> Optional[float]:
    """
    Convert a display value like '59K', '-2.5%', '1.2B' to a float.
    Returns None if the string cannot be meaningfully parsed.
    """
    if not value or value in ("-", "—", "N/A", ""):
        return None

    # Strip common suffixes
    multipliers = {
        "K": 1_000,
        "M": 1_000_000,
        "B": 1_000_000_000,
        "T": 1_000_000_000_000,
    }
    val = value.strip().replace(",", "").replace("%", "").replace("$", "")

    multiplier = 1
    if val and val[-1].upper() in multipliers:
        multiplier = multipliers[val[-1].upper()]
        val = val[:-1]

    try:
        return float(val) * multiplier
    except ValueError:
        return None
