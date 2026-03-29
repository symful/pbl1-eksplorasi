import json
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict

def _utc_now_rfc3339() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def _safe_int(s: str, default: int) -> int:
    try:
        return int(str(s).strip())
    except Exception:
        return default

def _pretty_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)

def _format_dt_str(iso_str: str) -> str:
    if not iso_str: return ""
    try:
        dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S " + dt.tzname())
    except:
        return str(iso_str)

def _event_to_dict(e: Any) -> Dict[str, Any]:
    """Convert EconomicEvent to a dict safe for JSON."""
    if hasattr(e, "to_dict"):
        return e.to_dict(include_raw=False)
    try:
        d = asdict(e)
    except Exception:
        d = dict(e) if isinstance(e, dict) else {"value": str(e)}

    dt = d.get("datetime_utc")
    if isinstance(dt, datetime):
        d["datetime_utc"] = dt.isoformat()
    return d
