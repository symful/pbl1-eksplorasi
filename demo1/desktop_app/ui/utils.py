import json
from datetime import datetime, timezone
from typing import Any, Dict


def utc_now_rfc3339() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def safe_int(s: str, default: int) -> int:
    try:
        return int(str(s).strip())
    except Exception:
        return default


def pretty_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def format_datetime(iso_str: str) -> str:
    if not iso_str:
        return ""
    try:
        s = str(iso_str).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(iso_str)


def event_to_dict(e: Any) -> Dict[str, Any]:
    if hasattr(e, "to_dict"):
        return e.to_dict(include_raw=False)
    try:
        from dataclasses import asdict
        d = asdict(e)
    except Exception:
        d = dict(e) if isinstance(e, dict) else {"value": str(e)}
    dt = d.get("datetime_utc")
    if isinstance(dt, datetime):
        d["datetime_utc"] = dt.isoformat()
    return d


def format_price(price: float | None, currency: str = "") -> str:
    if price is None:
        return "—"
    if abs(price) >= 10_000:
        formatted = f"{price:,.0f}"
    elif abs(price) >= 100:
        formatted = f"{price:,.2f}"
    else:
        formatted = f"{price:.4f}"
    return f"{formatted} {currency}" if currency else formatted


def format_change(change: float | None, pct: float | None) -> str:
    if change is None and pct is None:
        return "—"
    parts = []
    if change is not None:
        parts.append(f"{change:+.4g}")
    if pct is not None:
        parts.append(f"({pct:+.2f}%)")
    return " ".join(parts)
