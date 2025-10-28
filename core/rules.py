# core/rules.py
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List

CFG = {
    "failed_login_window_min": 60,
    "failed_per_user": 8,
    "failed_per_ip": 20,
    "impossible_travel_window": 90,
}


class RuleDetector:
    def __init__(self, cfg: Dict[str, Any] = None):
        self.cfg = {**CFG, **(cfg or {})}
        self.fail_user = defaultdict(deque)
        self.fail_ip = defaultdict(deque)
        self.last_country = {}

    def _ts(self, iso):
        if not iso:
            return None
        try:
            # Normalize trailing Z to explicit UTC offset for fromisoformat
            s = iso.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            # Force UTC on naive datetimes; convert aware datetimes to UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            return dt
        except Exception:
            return None

    def _prune(self, dq, now, minutes):
        cutoff = now - timedelta(minutes=minutes)
        while dq and dq[0] < cutoff:
            dq.popleft()

    def evaluate(self, evt: Dict[str, Any]) -> List[tuple]:
        out = []
        ts = self._ts(evt.get("timestamp"))
        outcome = (evt.get("outcome") or "").lower()

        if ts and outcome in ("failure", "failed", "denied"):
            dq_u = self.fail_user[evt.get("user")]
            dq_u.append(ts)
            self._prune(dq_u, ts, self.cfg["failed_login_window_min"])
            if len(dq_u) >= self.cfg["failed_per_user"]:
                out.append(
                    (
                        "excessive_failed_logins_user",
                        "medium",
                        f"user {evt.get('user')} failures={len(dq_u)}",
                    )
                )
            dq_i = self.fail_ip[evt.get("ip")]
            dq_i.append(ts)
            self._prune(dq_i, ts, self.cfg["failed_login_window_min"])
            if len(dq_i) >= self.cfg["failed_per_ip"]:
                out.append(
                    (
                        "excessive_failed_logins_ip",
                        "high",
                        f"ip {evt.get('ip')} failures={len(dq_i)}",
                    )
                )

        user = evt.get("user")
        country = (evt.get("country") or "").strip()
        if user and country and ts:
            last = self.last_country.get(user)
            self.last_country[user] = (country, ts)
            if last:
                lc, lt = last
                if (
                    lc
                    and lc != country
                    and (ts - lt) <= timedelta(minutes=self.cfg["impossible_travel_window"])
                ):
                    out.append(
                        ("impossible_travel", "high", f"{user}: {lc} -> {country} quickly")
                    )
        return out
