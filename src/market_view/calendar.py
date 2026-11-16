"""NSE trading calendar: trading days, session times (IST)."""

from __future__ import annotations

from datetime import date, datetime, time

from market_view.config import IST, get_settings


def _t(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def holidays() -> set[date]:
    return {date.fromisoformat(d) for d in get_settings().calendar.holidays}


def is_trading_day(d: date) -> bool:
    return d.weekday() < 5 and d not in holidays()


def session_times() -> tuple[time, time]:
    s = get_settings().calendar.session
    return _t(s["open"]), _t(s["close"])


def now_ist() -> datetime:
    return datetime.now(IST)


def is_market_open(at: datetime | None = None) -> bool:
    at = (at or now_ist()).astimezone(IST)
    if not is_trading_day(at.date()):
        return False
    open_t, close_t = session_times()
    return open_t <= at.time() <= close_t


def parse_hhmm(s: str) -> time:
    return _t(s)
