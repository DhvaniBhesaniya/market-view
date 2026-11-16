"""Configuration loading (YAML in config/, secrets in .env) and the live-trading guard."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, model_validator

IST = ZoneInfo("Asia/Kolkata")

ROOT = Path(os.environ.get("MARKET_VIEW_ROOT", Path(__file__).resolve().parents[2]))
CONFIG_DIR = ROOT / "config"
DATA_DIR = Path(os.environ.get("MARKET_VIEW_DATA", ROOT / "data"))
REPORTS_DIR = Path(os.environ.get("MARKET_VIEW_REPORTS", ROOT / "reports"))

load_dotenv(ROOT / ".env")


class LiveTradingDisabled(RuntimeError):
    """Raised whenever code tries to reach a real broker order endpoint without both switches."""


def live_trading_enabled(cli_flag: bool) -> bool:
    """Live orders need BOTH `LIVE_TRADING=true` in the environment AND an explicit `--live` flag.

    CLAUDE.md safety rule 1. Never call this with a hard-coded True.
    """
    env_ok = os.environ.get("LIVE_TRADING", "false").strip().lower() == "true"
    return env_ok and cli_flag is True


def require_live(cli_flag: bool) -> None:
    if not live_trading_enabled(cli_flag):
        raise LiveTradingDisabled(
            "Live trading is disabled. It requires LIVE_TRADING=true in .env AND the --live flag, "
            "and is only allowed after the Phase 5 gate (docs/04-roadmap.md)."
        )


def _load_yaml(name: str) -> dict[str, Any]:
    path = CONFIG_DIR / name
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class RiskConfig(BaseModel):
    risk_per_trade_pct: float = 0.25
    max_risk_per_trade_pct: float = 0.5
    max_open_positions: int = 5
    max_portfolio_heat_pct: float = 1.5
    max_positions_per_sector: int = 2
    max_position_value_pct: float = 20.0
    min_cash_buffer_pct: float = 5.0
    daily_loss_cap_pct: float = 1.0
    weekly_loss_cap_pct: float = 2.5
    strategy_drawdown_breaker_pct: float = 10.0
    portfolio_drawdown_breaker_pct: float = 12.0
    max_consecutive_losses: int = 6
    min_price: float = 50.0
    min_avg_turnover_cr: float = 50.0
    max_pct_of_adv: float = 1.0
    min_edge_to_cost_ratio: float = 4.0
    max_orders_per_second: int = 5
    blocked_symbols: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _sane(self) -> RiskConfig:
        if self.risk_per_trade_pct > self.max_risk_per_trade_pct:
            raise ValueError(
                f"risk_per_trade_pct {self.risk_per_trade_pct} exceeds ceiling "
                f"{self.max_risk_per_trade_pct}"
            )
        if self.max_orders_per_second > 10:
            raise ValueError("max_orders_per_second must stay below the SEBI threshold of 10")
        return self


class SegmentCosts(BaseModel):
    brokerage_flat: float
    brokerage_pct: float
    brokerage_min: float = 0.0
    brokerage_min_pct: float | None = None   # Groww: minimum is the LOWER of brokerage_min or this % of value
    stt_buy_pct: float
    stt_sell_pct: float
    exchange_txn_pct: float
    sebi_pct: float
    stamp_buy_pct: float
    gst_pct: float
    dp_charge_per_sell: float = 0.0


class CostConfig(BaseModel):
    delivery: SegmentCosts
    intraday: SegmentCosts
    slippage_bps: float = 5.0


class Period(BaseModel):
    start: str
    end: str | None = None


class WalkForwardConfig(BaseModel):
    train_years: int = 4
    test_years: int = 1
    first_test_year: int = 2014
    last_test_year: int = 2022


class MonteCarloConfig(BaseModel):
    runs: int = 1000
    seed: int = 42


class BacktestConfig(BaseModel):
    initial_capital: float = 500_000
    data_source: str = "yfinance"
    interval: str = "1d"
    benchmark: str = "NIFTY50"
    volatility_index: str = "INDIAVIX"
    warmup_days: int = 300
    periods: dict[str, Period]
    walkforward: WalkForwardConfig = WalkForwardConfig()
    montecarlo: MonteCarloConfig = MonteCarloConfig()


class PaperSchedule(BaseModel):
    open_job: str = "09:20"
    monitor_every_minutes: int = 5
    eod_job: str = "15:45"


class PaperConfig(BaseModel):
    initial_capital: float = 500_000
    product: str = "CNC"
    live_data_source: str = "auto"
    history_source: str = "auto"
    schedule: PaperSchedule = PaperSchedule()
    stale_data_seconds: int = 900


class SymbolInfo(BaseModel):
    isin: str | None = None
    sector: str = "Unknown"


class IndexInfo(BaseModel):
    yahoo: str
    upstox: str


class UniverseConfig(BaseModel):
    name: str
    fetched: str | None = None
    indices: dict[str, IndexInfo]
    symbols: dict[str, SymbolInfo]
    former_members: dict[str, SymbolInfo] = Field(default_factory=dict)

    def all_symbols(self, include_former: bool = True) -> list[str]:
        syms = list(self.symbols)
        if include_former:
            syms += [s for s in self.former_members if s not in self.symbols]
        return syms

    def info(self, symbol: str) -> SymbolInfo:
        return self.symbols.get(symbol) or self.former_members.get(symbol) or SymbolInfo()


class StrategiesConfig(BaseModel):
    enabled: list[str]
    params: dict[str, dict[str, Any]] = Field(default_factory=dict)


class CalendarConfig(BaseModel):
    session: dict[str, str]
    holidays: dict[str, str]


class Settings(BaseModel):
    risk: RiskConfig
    costs: CostConfig
    backtest: BacktestConfig
    paper: PaperConfig
    universe: UniverseConfig
    strategies: StrategiesConfig
    calendar: CalendarConfig


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        risk=RiskConfig(**_load_yaml("risk.yaml")),
        costs=CostConfig(**_load_yaml("costs.yaml")),
        backtest=BacktestConfig(**_load_yaml("backtest.yaml")),
        paper=PaperConfig(**_load_yaml("paper.yaml")),
        universe=UniverseConfig(**_load_yaml("universe.yaml")),
        strategies=StrategiesConfig(**_load_yaml("strategies.yaml")),
        calendar=CalendarConfig(**_load_yaml("nse_calendar.yaml")),
    )


def env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name, default)
    return value if value not in ("", None) else default
