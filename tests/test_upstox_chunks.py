"""Upstox V3 history limits are calendar-based (1 month for 1-15m, 1 quarter for 30m/hours, 1 decade for days).

A 30-day window spanning February is longer than one calendar month and is rejected with
UDAPI1148 "Invalid date range" (seen live on 2026-11-18), so chunks must be built by calendar months.
"""

from datetime import date

import pytest
from dateutil.relativedelta import relativedelta

from market_view.data.sources import upstox_source
from market_view.data.sources.upstox_source import UpstoxSource


@pytest.fixture
def recorder(monkeypatch):
    calls: list[tuple[date, date]] = []

    def fake_get(self, path, params=None):
        if "/intraday/" not in path:
            *_, to_s, from_s = path.split("/")
            calls.append((date.fromisoformat(from_s), date.fromisoformat(to_s)))
        return {"candles": []}

    monkeypatch.setattr(UpstoxSource, "_get", fake_get)
    monkeypatch.setattr(upstox_source, "instrument_key", lambda s: "NSE_EQ|TEST")
    return calls


@pytest.mark.parametrize("interval, months", [("15m", 1), ("5m", 1), ("1m", 1), ("30m", 3), ("1h", 3), ("1d", 120)])
def test_chunks_never_exceed_calendar_limit_and_cover_range(recorder, interval, months):
    start, end = date(2022, 1, 1), date(2026, 3, 23)
    UpstoxSource(token="x").history("TEST", interval, start, end)
    assert recorder, "no requests made"
    for frm, to in recorder:
        assert frm <= to
        assert frm > to - relativedelta(months=months), f"{frm}..{to} exceeds {months} calendar month(s)"
    # contiguous, no gaps or overlaps, exactly covering [start, end]
    ordered = sorted(recorder)
    assert ordered[0][0] == start and ordered[-1][1] == end
    for (_, prev_to), (nxt_from, _) in zip(ordered, ordered[1:], strict=False):
        assert (nxt_from - prev_to).days == 1


def test_february_window_that_failed_live_is_split(recorder):
    UpstoxSource(token="x").history("TEST", "15m", date(2026, 2, 22), date(2026, 3, 23))
    assert (date(2026, 2, 22), date(2026, 3, 23)) not in recorder
    assert len(recorder) == 2
