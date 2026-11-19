"""Upstox market data (read-only). Docs: https://upstox.com/developer/api-documentation

Auth: set UPSTOX_ACCESS_TOKEN in .env. Best for data: the **Analytics token** (Developer Apps page,
valid ~1 year, read-only GET APIs, cannot place orders, no static IP needed for market data).
Alternatively a daily OAuth token (expires 03:30 IST) via `mv upstox login-url` / `exchange-code`.

Historical V3: GET /v3/historical-candle/{key}/{unit}/{interval}/{to}/{from}
  days since 2000 (max 10 years per call); minutes/hours since Jan 2022
  (1-15 min: 1 month per call, >15 min & hours: 1 quarter per call).
Intraday V3:  GET /v3/historical-candle/intraday/{key}/{unit}/{interval}
LTP V3:       GET /v3/market-quote/ltp?instrument_key=a,b
Candle row:   [timestamp, open, high, low, close, volume, oi]   (newest first)

NOTE: Upstox historical prices are not guaranteed split-adjusted. `mv data validate` flags jumps.
"""

from __future__ import annotations

import math
import time
from datetime import date, datetime, timedelta
from urllib.parse import quote as urlquote

import pandas as pd
import requests
from dateutil.relativedelta import relativedelta

from market_view.config import IST, env, get_settings
from market_view.data.sources.base import DataSource, Quote, normalize

BASE = "https://api.upstox.com"

# interval -> (unit, interval, max CALENDAR months per request).
# Upstox V3 limits are calendar-based: 1 month (1-15 min), 1 quarter (>15 min, hours), 1 decade (days).
# A 30-day window spanning February exceeds "1 month" and fails with UDAPI1148 "Invalid date range".
_INTERVALS: dict[str, tuple[str, int, int]] = {
    "1d": ("days", 1, 120),
    "1h": ("hours", 1, 3),
    "60m": ("hours", 1, 3),
    "30m": ("minutes", 30, 3),
    "15m": ("minutes", 15, 1),
    "5m": ("minutes", 5, 1),
    "1m": ("minutes", 1, 1),
}


class UpstoxError(RuntimeError):
    pass


def instrument_key(symbol: str) -> str:
    u = get_settings().universe
    if symbol in u.indices:
        return u.indices[symbol].upstox
    info = u.info(symbol)
    if not info.isin:
        raise UpstoxError(f"no ISIN for {symbol}; add it to config/universe.yaml")
    return f"NSE_EQ|{info.isin}"


class UpstoxSource(DataSource):
    name = "upstox"
    adjusted = False

    def __init__(self, token: str | None = None, min_interval_s: float = 0.25) -> None:
        self.token = token or env("UPSTOX_ACCESS_TOKEN")
        if not self.token:
            raise UpstoxError("UPSTOX_ACCESS_TOKEN is not set in .env")
        self.session = requests.Session()
        self.session.headers.update(
            {"Accept": "application/json", "Authorization": f"Bearer {self.token}"}
        )
        self._min_interval = min_interval_s  # client-side throttle, well under Upstox limits
        self._last_call = 0.0

    def _get(self, path: str, params: dict | None = None) -> dict:
        wait = self._min_interval - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        for attempt in range(3):
            self._last_call = time.monotonic()
            resp = self.session.get(BASE + path, params=params, timeout=30)
            if resp.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            if resp.status_code == 401:
                raise UpstoxError("Upstox token invalid or expired (daily tokens expire 03:30 IST)")
            if resp.status_code >= 400:
                raise UpstoxError(f"Upstox {resp.status_code}: {resp.text[:300]}")
            body = resp.json()
            if body.get("status") != "success":
                raise UpstoxError(f"Upstox error: {str(body)[:300]}")
            return body.get("data", {})
        raise UpstoxError("Upstox rate limit: retries exhausted")

    @staticmethod
    def _candles_to_df(candles: list[list]) -> pd.DataFrame:
        if not candles:
            return normalize(pd.DataFrame())
        df = pd.DataFrame(candles, columns=["ts", "open", "high", "low", "close", "volume", "oi"][: len(candles[0])])
        df["ts"] = pd.to_datetime(df["ts"])
        return normalize(df.set_index("ts"))

    def history(self, symbol: str, interval: str, start: date, end: date) -> pd.DataFrame:
        if interval not in _INTERVALS:
            raise ValueError(f"unsupported interval {interval}")
        unit, n, max_months = _INTERVALS[interval]
        key = urlquote(instrument_key(symbol), safe="")
        frames = []
        chunk_end = end
        while chunk_end >= start:
            chunk_start = max(start, chunk_end - relativedelta(months=max_months) + timedelta(days=1))
            path = f"/v3/historical-candle/{key}/{unit}/{n}/{chunk_end.isoformat()}/{chunk_start.isoformat()}"
            frames.append(self._candles_to_df(self._get(path).get("candles", [])))
            chunk_end = chunk_start - timedelta(days=1)
        if end >= datetime.now(IST).date() and interval != "1d":
            path = f"/v3/historical-candle/intraday/{key}/{unit}/{n}"
            frames.append(self._candles_to_df(self._get(path).get("candles", [])))
        df = pd.concat([f for f in frames if not f.empty]) if any(not f.empty for f in frames) else normalize(pd.DataFrame())
        df = normalize(df)
        if interval == "1d" and not df.empty:
            df.index = pd.DatetimeIndex(
                [pd.Timestamp(d.date(), tz=IST) + pd.Timedelta(hours=9, minutes=15) for d in df.index],
                name="ts",
            )
        return df

    def intraday_today(self, symbol: str, interval: str = "5m") -> pd.DataFrame:
        unit, n, _ = _INTERVALS[interval]
        key = urlquote(instrument_key(symbol), safe="")
        return self._candles_to_df(self._get(f"/v3/historical-candle/intraday/{key}/{unit}/{n}").get("candles", []))

    def quotes(self, symbols: list[str]) -> dict[str, Quote]:
        """Executable snapshots use the exchange's last-trade time, never request time."""
        out: dict[str, Quote] = {}
        if not symbols:
            return out
        keys = {instrument_key(s): s for s in symbols}
        data = self._get("/v3/market-quote/quotes", {"instrument_key": ",".join(keys)})
        for item in data.values():
            sym = keys.get(item.get("instrument_token"))
            if sym is None:
                continue
            try:
                timestamp = float(item["last_trade_time"]) / 1000
                ltp = float(item["last_price"])
                if timestamp <= 0 or not math.isfinite(ltp) or ltp <= 0:
                    continue
                when = datetime.fromtimestamp(timestamp, IST)
            except (KeyError, TypeError, ValueError, OSError, OverflowError):
                continue
            ohlc = item.get("ohlc") or {}
            out[sym] = Quote(symbol=sym, ltp=ltp, open=ohlc.get("open"), high=ohlc.get("high"),
                             low=ohlc.get("low"), prev_close=item.get("prev_close_price"), time=when)
        return out

    def check(self) -> dict:
        """Cheap auth check: fetch NIFTY 50 LTP."""
        return self._get("/v3/market-quote/ltp", {"instrument_key": instrument_key("NIFTY50")})


# --- OAuth helpers (daily token flow). Analytics token users don't need these. ---------------

def login_url() -> str:
    client_id = env("UPSTOX_API_KEY")
    redirect = env("UPSTOX_REDIRECT_URI", "http://127.0.0.1:8765/callback")
    if not client_id:
        raise UpstoxError("UPSTOX_API_KEY not set in .env")
    return (
        f"{BASE}/v2/login/authorization/dialog?response_type=code"
        f"&client_id={client_id}&redirect_uri={urlquote(redirect, safe='')}"
    )


def exchange_code(code: str) -> str:
    """Exchange the ?code=... from the redirect URL for an access token (valid until 03:30 IST)."""
    resp = requests.post(
        f"{BASE}/v2/login/authorization/token",
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
        data={
            "code": code,
            "client_id": env("UPSTOX_API_KEY"),
            "client_secret": env("UPSTOX_API_SECRET"),
            "redirect_uri": env("UPSTOX_REDIRECT_URI", "http://127.0.0.1:8765/callback"),
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    if resp.status_code >= 400:
        raise UpstoxError(f"token exchange failed {resp.status_code}: {resp.text[:300]}")
    token = resp.json().get("access_token")
    if not token:
        raise UpstoxError("no access_token in response")
    return token
