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
      - handle quoted values with simple escape sequences (\" and \\)
      - fall back to bare non-space tokens for unquoted values
    """
    out: Dict[str, Any] = {}
    # keys: letters/digits/underscore/dot
    # values: " ... (with escaped quotes) ..."  OR  non-space token
    pattern = r'([\w\.]+)=("([^"\\]|\\.)*"|\S+)'
    for m in re.finditer(pattern, line):
        k, v = m.group(1), m.group(2)
        if v.startswith('"') and v.endswith('"'):
            # strip quotes and unescape
            v = v[1:-1]
            v = v.replace(r'\"', '"').replace(r'\\', '\\')
        out[k] = v
    return out


def _to_iso(ts: Any) -> Optional[str]:
    """
    Convert various timestamp forms to ISO-8601 (UTC).
    Supports:
      - epoch seconds (10 digits) or epoch millis (13 digits) -> UTC
      - ISO strings with 'Z' or timezone (converted to UTC)
      - naive ISO strings (treated as UTC)
    Returns None if parsing fails.
    """
    if ts is None:
        return None

    s = str(ts).strip()

    # epoch millis
    if re.fullmatch(r"\d{13}", s):
        try:
            dt = datetime.datetime.utcfromtimestamp(int(s) / 1000.0).replace(
                tzinfo=datetime.timezone.utc
            )
            return dt.isoformat()
        except Exception:
            return None

    # epoch seconds
    if re.fullmatch(r"\d{10}", s):
        try:
            dt = datetime.datetime.utcfromtimestamp(int(s)).replace(
                tzinfo=datetime.timezone.utc
            )
            return dt.isoformat()
        except Exception:
            return None

    # ISO-like: normalize trailing Z and convert to UTC
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


def load_okta_logs(path: str = "okta-logs.txt") -> List[Dict[str, Any]]:
    """
    Load Okta events from a file that may contain JSONL or key=value lines.
    - Enumerates lines for precise warnings on skips
    - Attempts JSON first; if it fails, attempts key=value parsing
    """
    events: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for i, raw in enumerate(f):
            raw = raw.strip()
            if not raw:
                continue

            # Try JSON first
            try:
                obj = json.loads(raw)
                if isinstance(obj, dict):
                    events.append(obj)
                    continue
            except Exception:
                # JSON failed; try K-V
                pass

            kv = parse_kv_line(raw)
            if kv:
                events.append(kv)
            else:
                logging.warning(f"Skipped unparseable line {i + 1} in {path}")
    return events


def normalize_event(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize raw Okta event to a flat schema used by rules:
      - timestamp (ISO-8601 or None)
      - event_type
      - message
      - user
      - ip
      - country
      - outcome
      - raw (original dict)
    """
    def get(d: Dict[str, Any], path: str, default=None):
        cur: Any = d
        for p in path.split("."):
            if isinstance(cur, dict) and p in cur:
                cur = cur[p]
            else:
                return default
        return cur

    event_type = raw.get("eventType") or raw.get("type")
    display = raw.get("displayMessage") or raw.get("message") or raw.get("msg")
    user = get(raw, "actor.alternateId") or raw.get("user") or raw.get("actor")
    ip = get(raw, "client.ipAddress") or raw.get("ip")
    country = get(raw, "client.geographicalContext.country") or raw.get("country")
    outcome = get(raw, "outcome.result") or raw.get("result")

    # Pull common time fields and normalize
    ts = (
        raw.get("published")
        or raw.get("eventTime")
        or raw.get("time")
        or raw.get("timestamp")
    )
    iso = _to_iso(ts) if ts is not None else None

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
    """
    Load, normalize, and chronologically sort events.
    Sorting key pushes None timestamps to the end to avoid skewing
    stateful rules (e.g., impossible travel's 'first seen' location).
    """
    evts = load_okta_logs(path)
    normalized = [normalize_event(e) for e in evts]

    # Stable sort: (None timestamps last), then lexicographic ISO
    normalized.sort(key=lambda x: (x.get("timestamp") is None, x.get("timestamp") or ""))

    return normalized
