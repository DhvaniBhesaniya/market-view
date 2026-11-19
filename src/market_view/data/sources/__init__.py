"""Market data sources. Every source returns the same normalized OHLCV DataFrame."""

from __future__ import annotations

from market_view.config import env
from market_view.data.sources.base import DataSource, Quote


def get_source(name: str = "auto") -> DataSource:
    """`auto` picks Upstox when an access token is configured, else free yfinance."""
    if name == "auto":
        name = "upstox" if env("UPSTOX_ACCESS_TOKEN") else "yfinance"
    if name == "yfinance":
        from market_view.data.sources.yfinance_source import YFinanceSource

        return YFinanceSource()
    if name == "upstox":
        from market_view.data.sources.upstox_source import UpstoxSource

        return UpstoxSource()
    raise ValueError(f"unknown data source {name!r}")


__all__ = ["DataSource", "Quote", "get_source"]
