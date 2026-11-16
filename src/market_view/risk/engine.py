"""Risk engine: veto power over every trade (CLAUDE.md rule 3). See docs/05-risk-management.md.

Used identically by the backtester and the paper/live execution path.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from market_view.config import RiskConfig, get_settings
from market_view.costs import CostModel
from market_view.models import RiskDecision, Signal


def position_size(equity: float, risk_pct: float, entry: float, stop: float) -> int:
    """Fixed-fractional sizing: qty = (equity x risk%) / (entry - stop), rounded DOWN.

    Example: Rs 5,00,000 x 0.25% = Rs 1,250 risk; entry 1000, stop 972 -> 28/share -> 44 shares.
    A volatile stock has a wider ATR stop, so it automatically gets fewer shares.
    """
    per_share = entry - stop
    if per_share <= 0 or entry <= 0:
        return 0
    return max(0, math.floor(equity * risk_pct / 100 / per_share))


@dataclass
class OpenRisk:
    symbol: str
    strategy_id: str
    sector: str
    qty: int
    entry: float
    stop: float
    last_price: float

    @property
    def risk(self) -> float:
        """Rupees lost if the stop is hit now (0 once the stop is above entry)."""
        return max(0.0, (self.entry - self.stop) * self.qty)

    @property
    def value(self) -> float:
        return self.last_price * self.qty


@dataclass
class PortfolioState:
    equity: float
    cash: float
    peak_equity: float
    day_start_equity: float
    week_start_equity: float
    positions: list[OpenRisk] = field(default_factory=list)
    pending_symbols: set[str] = field(default_factory=set)
    strategy_peak: dict[str, float] = field(default_factory=dict)      # strategy cumulative pnl peak
    strategy_pnl: dict[str, float] = field(default_factory=dict)       # strategy cumulative net pnl
    consecutive_losses: dict[str, int] = field(default_factory=dict)
    disabled_strategies: dict[str, str] = field(default_factory=dict)  # id -> reason
    killswitch_active: bool = False

    @property
    def drawdown_pct(self) -> float:
        return 0.0 if self.peak_equity <= 0 else (self.peak_equity - self.equity) / self.peak_equity * 100

    @property
    def day_pnl_pct(self) -> float:
        return (self.equity - self.day_start_equity) / self.day_start_equity * 100

    @property
    def week_pnl_pct(self) -> float:
        return (self.equity - self.week_start_equity) / self.week_start_equity * 100


class RiskEngine:
    def __init__(self, cfg: RiskConfig | None = None, costs: CostModel | None = None,
                 sectors: dict[str, str] | None = None, initial_capital: float | None = None) -> None:
        self.cfg = cfg or get_settings().risk
        self.costs = costs or CostModel()
        if sectors is None:
            u = get_settings().universe
            sectors = {s: u.info(s).sector for s in u.all_symbols()}
        self.sectors = sectors
        self.initial_capital = initial_capital

    def sector(self, symbol: str) -> str:
        return self.sectors.get(symbol, "Unknown")

    # ------------------------------------------------------------------ pre-trade
    def check(self, signal: Signal, price: float, state: PortfolioState) -> RiskDecision:
        """Decide whether `signal` may be entered at `price`, and how many shares."""
        c = self.cfg
        no: list[str] = []

        if state.killswitch_active:
            return RiskDecision(approved=False, reasons=["kill switch active"])
        if signal.strategy_id in state.disabled_strategies:
            return RiskDecision(approved=False, reasons=[f"strategy disabled: {state.disabled_strategies[signal.strategy_id]}"])
        if signal.symbol in c.blocked_symbols:
            no.append("symbol blocked")
        if signal.stop is None or not signal.stop < price:
            no.append(f"stop {signal.stop} not below price {price:.2f} (gap through stop?)")
        if price < c.min_price:
            no.append(f"price {price:.2f} < min {c.min_price}")
        if state.day_pnl_pct <= -c.daily_loss_cap_pct:
            no.append(f"daily loss cap hit ({state.day_pnl_pct:.2f}%)")
        if state.week_pnl_pct <= -c.weekly_loss_cap_pct:
            no.append(f"weekly loss cap hit ({state.week_pnl_pct:.2f}%)")
        if state.drawdown_pct >= c.portfolio_drawdown_breaker_pct:
            no.append(f"portfolio drawdown {state.drawdown_pct:.1f}% >= breaker")
        if len(state.positions) >= c.max_open_positions:
            no.append(f"max open positions {c.max_open_positions}")
        if any(p.symbol == signal.symbol for p in state.positions) or signal.symbol in state.pending_symbols:
            no.append("already in position / pending for symbol")
        sector = self.sector(signal.symbol)
        if sum(1 for p in state.positions if p.sector == sector) >= c.max_positions_per_sector:
            no.append(f"sector limit ({sector})")
        turnover = signal.context.get("turnover_cr")
        if turnover is not None and turnover < c.min_avg_turnover_cr:
            no.append(f"illiquid: avg turnover Rs {turnover:.0f} cr < {c.min_avg_turnover_cr}")
        if no:
            return RiskDecision(approved=False, reasons=no)

        # sizing
        qty = position_size(state.equity, c.risk_per_trade_pct, price, signal.stop)
        notes: list[str] = []
        max_value = state.equity * c.max_position_value_pct / 100
        if qty * price > max_value:
            qty = math.floor(max_value / price)
            notes.append(f"resized to {c.max_position_value_pct}% position cap")
        spendable = state.cash - state.equity * c.min_cash_buffer_pct / 100
        est_cost = self.costs.charges("BUY", qty * price)
        if qty * price + est_cost > spendable:
            qty = max(0, math.floor((spendable - est_cost) / price))
            notes.append("resized to available cash")
        adv = signal.context.get("adv20")
        if adv:
            max_qty = math.floor(adv * c.max_pct_of_adv / 100)
            if qty > max_qty:
                qty = max_qty
                notes.append(f"resized to {c.max_pct_of_adv}% of avg daily volume")
        if qty < 1:
            return RiskDecision(approved=False, reasons=["position size < 1 share", *notes])

        risk_amount = (price - signal.stop) * qty
        heat = sum(p.risk for p in state.positions) + risk_amount
        if heat > state.equity * c.max_portfolio_heat_pct / 100:
            return RiskDecision(approved=False, reasons=[f"portfolio heat {heat / state.equity * 100:.2f}% > {c.max_portfolio_heat_pct}%"])

        # cost-vs-edge: expected move (target, or 2R if trailing) must dwarf round-trip costs
        target = signal.target if signal.target else price + 2 * (price - signal.stop)
        edge = (target - price) * qty
        rt_cost = self.costs.round_trip(price, target, qty)
        if edge < c.min_edge_to_cost_ratio * rt_cost:
            return RiskDecision(approved=False, reasons=[f"edge Rs {edge:.0f} < {c.min_edge_to_cost_ratio}x costs Rs {rt_cost:.0f}"])

        return RiskDecision(approved=True, qty=qty, reasons=notes, risk_amount=risk_amount)

    # ------------------------------------------------------------------ post-trade
    def on_trade_closed(self, state: PortfolioState, strategy_id: str, net_pnl: float) -> list[str]:
        """Update per-strategy breakers. Returns human-readable events."""
        events: list[str] = []
        pnl = state.strategy_pnl.get(strategy_id, 0.0) + net_pnl
        state.strategy_pnl[strategy_id] = pnl
        state.strategy_peak[strategy_id] = max(state.strategy_peak.get(strategy_id, 0.0), pnl)
        base = self.initial_capital or state.peak_equity
        dd_pct = (state.strategy_peak[strategy_id] - pnl) / base * 100
        state.consecutive_losses[strategy_id] = (
            state.consecutive_losses.get(strategy_id, 0) + 1 if net_pnl < 0 else 0
        )
        if dd_pct >= self.cfg.strategy_drawdown_breaker_pct and strategy_id not in state.disabled_strategies:
            state.disabled_strategies[strategy_id] = f"strategy drawdown {dd_pct:.1f}% of capital"
            events.append(f"{strategy_id} DISABLED: drawdown breaker")
        if state.consecutive_losses[strategy_id] >= self.cfg.max_consecutive_losses and strategy_id not in state.disabled_strategies:
            state.disabled_strategies[strategy_id] = f"{state.consecutive_losses[strategy_id]} consecutive losses"
            events.append(f"{strategy_id} PAUSED: consecutive losses")
        return events

    def portfolio_breaker(self, state: PortfolioState) -> str | None:
        if state.drawdown_pct >= self.cfg.portfolio_drawdown_breaker_pct:
            return f"portfolio drawdown {state.drawdown_pct:.1f}% >= {self.cfg.portfolio_drawdown_breaker_pct}%"
        if state.day_pnl_pct <= -self.cfg.daily_loss_cap_pct:
            return f"daily loss {state.day_pnl_pct:.2f}% hit cap"
        return None
