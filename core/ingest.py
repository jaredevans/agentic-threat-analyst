# core/ingest.py
import json
import re
import datetime
import logging
from typing import List, Dict, Any, Optional


def parse_kv_line(line: str) -> Dict[str, Any]:
    """
    Parse key=value pairs from a single line.
    Improvements:
      - allow dotted keys (e.g., client.ipAddress)
      - handle quoted values with escape sequences
      - fallback to bare tokens
    """
    out: Dict[str, Any] = {}
    pattern = r'([\w\.]+)=("([^"\\]|\\.)*"|\S+)'
    for m in re.finditer(pattern, line):
        k, v = m.group(1), m.group(2)
        if v.startswith('"') and v.endswith('"'):
            v = v[1:-1].replace(r'\"', '"').replace(r'\\', '\\')
        out[k] = v
    return out


def _to_iso(ts: Any) -> Optional[str]:
    """Convert timestamps to ISO-8601 UTC."""
    if ts is None:
        return None
    s = str(ts).strip()

    # Epoch millis
    if re.fullmatch(r"\d{13}", s):
        try:
            dt = datetime.datetime.utcfromtimestamp(int(s) / 1000).replace(
                tzinfo=datetime.timezone.utc
            )
            return dt.isoformat()
        except Exception:
            return None

    # Epoch seconds
    if re.fullmatch(r"\d{10}", s):
        try:
            dt = datetime.datetime.utcfromtimestamp(int(s)).replace(
                tzinfo=datetime.timezone.utc
            )
            return dt.isoformat()
        except Exception:
            return None

    # ISO-like
    try:
        s2 = s.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(s2)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        else:
            dt = dt.astimezone(datetime.timezone.utc)
        return dt.isoformat()
    except Exception:
        return None


def _deep_get(obj: Any, path: str, default=None):
    """
    Retrieve nested dictionary or list value using dotted path with optional indices.
    Example: get(obj, "request.ipChain.0.geographicalContext.country")
    """
    cur = obj
    for p in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(p)
        elif isinstance(cur, list):
            try:
                idx = int(p)
                cur = cur[idx]
            except (ValueError, IndexError):
                return default
        else:
            return default
        if cur is None:
            return default
    return cur


def load_okta_logs(path: str = "okta-logs.txt") -> List[Dict[str, Any]]:
    """Load Okta events from JSONL or key=value lines."""
    events: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for i, raw in enumerate(f):
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
                if isinstance(obj, dict):
                    events.append(obj)
                    continue
            except Exception:
                pass

            kv = parse_kv_line(raw)
            if kv:
                events.append(kv)
            else:
                logging.warning(f"Skipped unparseable line {i + 1} in {path}")
    return events


def normalize_event(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize Okta event to standard schema:
      - timestamp (ISO-8601)
      - event_type
      - message
      - user
      - ip
      - country
      - outcome
      - raw
    """
    get = _deep_get
    event_type = raw.get("eventType") or raw.get("type")
    display = raw.get("displayMessage") or raw.get("message") or raw.get("msg")

    # actor info
    user = get(raw, "actor.alternateId") or raw.get("user") or raw.get("actor")

    # flexible IP/country extraction
    ip = (
        get(raw, "client.ipAddress")
        or get(raw, "request.ipChain.0.ip")
        or raw.get("ip")
    )
    country = (
        get(raw, "client.geographicalContext.country")
        or get(raw, "request.ipChain.0.geographicalContext.country")
        or raw.get("country")
    )
    outcome = get(raw, "outcome.result") or raw.get("result")

    ts = (
        raw.get("published")
        or raw.get("eventTime")
        or raw.get("time")
        or raw.get("timestamp")
    )
    iso = _to_iso(ts)

    return {
        "timestamp": iso,
        "event_type": event_type,
        "message": display,
        "user": user,
        "ip": ip,
        "country": country,
        "outcome": outcome,
        "raw": raw,
    }


def load_and_normalize(path: str = "okta-logs.txt") -> List[Dict[str, Any]]:
    """Load, normalize, and sort chronologically."""
    evts = load_okta_logs(path)
    normalized = [normalize_event(e) for e in evts]
    normalized.sort(key=lambda x: (x.get("timestamp") is None, x.get("timestamp") or ""))
    return normalized
