"""Free Yahoo Finance data via yfinance. Good for daily history; intraday is limited
(1m: last 7 days, 5m-60m: last 60 days). Quotes are delayed ~15 minutes. Not exchange-grade."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd

from market_view.config import IST, get_settings
from market_view.data.sources.base import DataSource, Quote, normalize

_INTERVALS = {"1d": "1d", "1h": "60m", "60m": "60m", "30m": "30m", "15m": "15m", "5m": "5m", "1m": "1m"}


def yahoo_ticker(symbol: str) -> str:
    indices = get_settings().universe.indices
    if symbol in indices:
        return indices[symbol].yahoo
    return f"{symbol}.NS"


class YFinanceSource(DataSource):
    name = "yfinance"
    adjusted = True  # auto_adjust=True: splits and dividends adjusted

    def history(self, symbol: str, interval: str, start: date, end: date) -> pd.DataFrame:
        import yfinance as yf

        if interval not in _INTERVALS:
            raise ValueError(f"unsupported interval {interval}")
        raw = yf.download(
            yahoo_ticker(symbol),
            start=start.isoformat(),
            end=(end + timedelta(days=1)).isoformat(),  # yfinance end is exclusive
            interval=_INTERVALS[interval],
            auto_adjust=True,
            progress=False,
            threads=False,
            multi_level_index=False,
        )
        if raw is None or raw.empty:
            return normalize(pd.DataFrame())
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        df = normalize(raw)
        if interval == "1d":
            # daily bars: stamp at session open 09:15 IST so all sources agree
            df.index = pd.DatetimeIndex(
                [pd.Timestamp(d.date(), tz=IST) + pd.Timedelta(hours=9, minutes=15) for d in df.index],
                name="ts",
            )
        return df

    def quotes(self, symbols: list[str]) -> dict[str, Quote]:
        import yfinance as yf

        out: dict[str, Quote] = {}
        for sym in symbols:
            raw = yf.download(
                yahoo_ticker(sym), period="5d", interval="5m", auto_adjust=False,
                progress=False, threads=False, multi_level_index=False,
            )
            if raw is None or raw.empty:
                continue
            df = normalize(raw)
            today = df[df.index.date == df.index[-1].date()]
            prev = df[df.index.date < df.index[-1].date()]
            out[sym] = Quote(
                symbol=sym,
                ltp=float(today["close"].iloc[-1]),
                open=float(today["open"].iloc[0]),
                high=float(today["high"].max()),
                low=float(today["low"].min()),
                prev_close=float(prev["close"].iloc[-1]) if not prev.empty else None,
                time=today.index[-1].to_pydatetime().astimezone(IST)
                + timedelta(minutes=5),  # bar open -> bar close
            )
        return out


def _now() -> datetime:
    return datetime.now(IST)
