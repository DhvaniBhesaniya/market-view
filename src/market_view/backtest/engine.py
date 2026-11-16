"""Event-driven, bar-by-bar portfolio backtester (the source of truth; vectorbt is for screening).

Honesty rules (CLAUDE.md #8, docs/06 section 3):
  * signal computed on bar t close -> entry at bar t+1 OPEN (never the signal bar's close)
  * entry skipped if the open gaps below the stop
  * open gaps through an existing stop -> exit at the open (worse than the stop)
  * stop and target both inside one bar -> assume the STOP hit first
  * every fill pays slippage + full Indian charges
  * the same RiskEngine as paper/live sizes and vetoes every entry
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd

from market_view.costs import CostModel
from market_view.models import Side, Signal, Trade
from market_view.risk.engine import OpenRisk, PortfolioState, RiskEngine
from market_view.strategies.base import PositionView, Strategy


@dataclass
class _Pos:
    symbol: str
    strategy: Strategy
    signal: Signal
    qty: int
    initial_qty: int
    entry_price: float
    entry_time: pd.Timestamp
    initial_stop: float
    stop: float
    target: float | None
    highest_high: float
    lowest_low: float
    bars_held: int = 0
    scaled_out: bool = False
    exit_qty: int = 0
    exit_value: float = 0.0
    charges: float = 0.0
    exit_next_open: str | None = None

    def view(self) -> PositionView:
        return PositionView(
            symbol=self.symbol, qty=self.qty, entry_price=self.entry_price,
            entry_time=self.entry_time.to_pydatetime(), initial_stop=self.initial_stop, stop=self.stop,
            target=self.target, bars_held=self.bars_held, highest_high=self.highest_high,
            scaled_out=self.scaled_out,
        )


@dataclass
class BacktestResult:
    equity: pd.Series
    trades: list[Trade]
    signals: pd.DataFrame
    benchmark: pd.Series | None
    events: list[str]
    params: dict[str, Any] = field(default_factory=dict)

    def trades_df(self) -> pd.DataFrame:
        return pd.DataFrame([t.model_dump() for t in self.trades])


class Backtester:
    def __init__(
        self,
        strategies: list[Strategy],
        data: dict[str, pd.DataFrame],
        start: date,
        end: date,
        initial_capital: float = 500_000,
        market: pd.DataFrame | None = None,
        risk: RiskEngine | None = None,
        costs: CostModel | None = None,
        product: str = "CNC",
        enforce_breakers: bool = False,
    ) -> None:
        """enforce_breakers=False (research default): strategy/portfolio breakers are RECORDED as
        'WOULD ...' events and the strategy resumes (as if reviewed), so years of data are not
        hidden behind one early losing streak. True = halt exactly as live trading would."""
        self.strategies = strategies
        self.data = data
        self.start, self.end = start, end
        self.capital = initial_capital
        self.market = market
        self.costs = costs or CostModel()
        self.risk = risk or RiskEngine(costs=self.costs, initial_capital=initial_capital)
        self.product = product
        self.enforce_breakers = enforce_breakers

    # ------------------------------------------------------------------ helpers
    def _buy(self, price: float, qty: int) -> tuple[float, float]:
        fill = self.costs.fill_price(Side.BUY, price)
        return fill, self.costs.charges(Side.BUY, fill * qty, self.product)

    def _sell(self, price: float, qty: int) -> tuple[float, float]:
        fill = self.costs.fill_price(Side.SELL, price)
        return fill, self.costs.charges(Side.SELL, fill * qty, self.product)

    # ------------------------------------------------------------------ run
    def run(self) -> BacktestResult:
        prepared: dict[str, dict[str, pd.DataFrame]] = {
            s.id: {sym: s.prepare(df, self.market) for sym, df in self.data.items() if len(df) > s.warmup_bars // 2}
            for s in self.strategies
        }
        strat_by_id = {s.id: s for s in self.strategies}

        # where entries fired: ts -> [(strategy_id, symbol)]
        entries_at: dict[pd.Timestamp, list[tuple[str, str]]] = defaultdict(list)
        for sid, by_sym in prepared.items():
            for sym, p in by_sym.items():
                for ts in p.index[p["entry"].to_numpy(dtype=bool)]:
                    entries_at[ts].append((sid, sym))

        bars: dict[str, dict[pd.Timestamp, tuple[float, float, float, float]]] = {
            sym: dict(zip(df.index, zip(df["open"], df["high"], df["low"], df["close"], strict=True), strict=True))
            for sym, df in self.data.items()
        }
        all_ts = sorted({ts for df in self.data.values() for ts in df.index if self.start <= ts.date() <= self.end})

        cash = self.capital
        state = PortfolioState(equity=cash, cash=cash, peak_equity=cash, day_start_equity=cash, week_start_equity=cash)
        positions: dict[str, _Pos] = {}
        pending: list[Signal] = []
        last_close: dict[str, float] = {}
        equity_curve: dict[pd.Timestamp, float] = {}
        trades: list[Trade] = []
        signal_log: list[dict] = []
        events: list[str] = []
        prev_week = None

        def close_pos(pos: _Pos, price: float, ts: pd.Timestamp, reason: str) -> None:
            nonlocal cash
            qty = pos.qty
            fill, ch = self._sell(price, qty)
            cash += fill * qty - ch
            pos.exit_qty += qty
            pos.exit_value += fill * qty
            pos.charges += ch
            pos.qty = 0
            gross = pos.exit_value - pos.entry_price * pos.initial_qty
            net = gross - pos.charges
            r_den = (pos.entry_price - pos.initial_stop) * pos.initial_qty
            trades.append(Trade(
                strategy_id=pos.strategy.id, symbol=pos.symbol,
                entry_time=pos.entry_time.to_pydatetime(), exit_time=ts.to_pydatetime(),
                entry_price=pos.entry_price, exit_price=pos.exit_value / pos.exit_qty,
                qty=pos.initial_qty, initial_stop=pos.initial_stop, target=pos.target,
                gross_pnl=gross, charges=pos.charges, net_pnl=net,
                r_multiple=net / r_den if r_den > 0 else 0.0, bars_held=pos.bars_held,
                # excursions while held, including the exit price itself (a gap exit IS the worst point)
                mae_pct=(min(pos.lowest_low, price) / pos.entry_price - 1) * 100,
                mfe_pct=(max(pos.highest_high, price) / pos.entry_price - 1) * 100,
                exit_reason=reason, reasons=pos.signal.reasons, context=pos.signal.context,
            ))
            del positions[pos.symbol]
            sid = pos.strategy.id
            fired = self.risk.on_trade_closed(state, sid, net)
            if fired and not self.enforce_breakers:
                # record, then simulate "reviewed and resumed"
                state.disabled_strategies.pop(sid, None)
                state.consecutive_losses[sid] = 0
                state.strategy_peak[sid] = state.strategy_pnl[sid]
                fired = [f"WOULD {e}" for e in fired]
            events.extend(f"{ts.date()} {e}" for e in fired)

        def sync_state() -> None:
            state.cash = cash
            state.positions = [
                OpenRisk(p.symbol, p.strategy.id, self.risk.sector(p.symbol), p.qty, p.entry_price, p.stop,
                         last_close.get(p.symbol, p.entry_price))
                for p in positions.values()
            ]
            state.equity = cash + sum(p.qty * last_close.get(p.symbol, p.entry_price) for p in positions.values())

        for ts in all_ts:
            week = ts.isocalendar()[:2]
            sync_state()
            state.day_start_equity = state.equity
            if week != prev_week:
                state.week_start_equity = state.equity
                prev_week = week

            # 1) pending exits at the open
            for pos in list(positions.values()):
                bar = bars[pos.symbol].get(ts)
                if pos.exit_next_open and bar:
                    close_pos(pos, bar[0], ts, pos.exit_next_open)

            # 2) pending entries at the open, best confidence first
            new_today: set[str] = set()
            state.pending_symbols = set()
            for sig in sorted(pending, key=lambda s: -s.confidence):
                bar = bars[sig.symbol].get(ts)
                log = {"ts": ts, "strategy_id": sig.strategy_id, "symbol": sig.symbol,
                       "confidence": sig.confidence, "ref_price": sig.ref_price, "stop": sig.stop}
                if bar is None:
                    signal_log.append({**log, "approved": False, "qty": 0, "reasons": "no bar next day"})
                    continue
                if bar[0] <= sig.stop:  # the RAW open is already through the stop: never enter
                    signal_log.append({**log, "approved": False, "qty": 0,
                                       "reasons": f"gapped below stop (open {bar[0]:.2f} <= stop {sig.stop:.2f})"})
                    continue
                sync_state()
                fill, _ = self._buy(bar[0], 1)
                decision = self.risk.check(sig, fill, state)
                signal_log.append({**log, "approved": decision.approved, "qty": decision.qty,
                                   "reasons": "; ".join(decision.reasons)})
                if not decision.approved:
                    continue
                qty = decision.qty
                fill, ch = self._buy(bar[0], qty)
                cash -= fill * qty + ch
                positions[sig.symbol] = _Pos(
                    symbol=sig.symbol, strategy=strat_by_id[sig.strategy_id], signal=sig, qty=qty,
                    initial_qty=qty, entry_price=fill, entry_time=ts, initial_stop=sig.stop, stop=sig.stop,
                    target=sig.target, highest_high=bar[1], lowest_low=bar[2], charges=ch,
                )
                new_today.add(sig.symbol)
                last_close.setdefault(sig.symbol, fill)
            pending = []

            # 3) manage open positions through today's bar
            for pos in list(positions.values()):
                bar = bars[pos.symbol].get(ts)
                if bar is None:
                    continue
                o, h, low, c = bar
                is_new = pos.symbol in new_today
                if not is_new and o <= pos.stop:
                    close_pos(pos, o, ts, "gap through stop")
                    continue
                if low <= pos.stop:  # pessimistic: stop before target within the same bar
                    close_pos(pos, pos.stop, ts, "stop" if pos.stop < pos.entry_price else "trailing stop")
                    continue
                strat = pos.strategy
                if strat.scale_out_r and not pos.scaled_out:
                    level = pos.entry_price + strat.scale_out_r * (pos.entry_price - pos.initial_stop)
                    if h >= level:
                        q = math.floor(pos.qty * strat.scale_out_fraction)
                        if q >= 1:
                            px = max(level, o) if not is_new else level
                            fill, ch = self._sell(px, q)
                            cash += fill * q - ch
                            pos.qty -= q
                            pos.exit_qty += q
                            pos.exit_value += fill * q
                            pos.charges += ch
                        pos.scaled_out = True
                        pos.stop = max(pos.stop, pos.entry_price)  # breakeven on the rest
                if pos.target and h >= pos.target:
                    close_pos(pos, max(pos.target, o) if not is_new else pos.target, ts, "target")
                    continue
                pos.highest_high = max(pos.highest_high, h)
                pos.lowest_low = min(pos.lowest_low, low)
                pos.bars_held += 1
                row = prepared[strat.id][pos.symbol].loc[ts]
                m = strat.manage(pos.view(), row)
                if m.new_stop is not None and m.new_stop > pos.stop:
                    pos.stop = m.new_stop
                if m.exit_next_open:
                    pos.exit_next_open = m.reason or "strategy exit"

            # 4) mark to market
            for sym, b in bars.items():
                if ts in b:
                    last_close[sym] = b[ts][3]
            sync_state()
            state.peak_equity = max(state.peak_equity, state.equity)
            equity_curve[ts] = state.equity
            breaker = self.risk.portfolio_breaker(state)
            # drawdown breaker AND daily loss cap: paper trading latches the kill switch for both
            if breaker and not state.killswitch_active:
                if self.enforce_breakers:
                    state.killswitch_active = True
                    events.append(f"{ts.date()} KILL SWITCH: {breaker}")
                else:
                    events.append(f"{ts.date()} WOULD KILL SWITCH: {breaker}")
                    if "drawdown" in breaker:
                        state.peak_equity = state.equity  # resume after "review"

            # 5) new signals on today's close -> tomorrow's open
            for sid, sym in entries_at.get(ts, []):
                if sym in positions or any(p.symbol == sym for p in pending):
                    continue
                sig = strat_by_id[sid].signal_at(prepared[sid][sym], ts, sym)
                if sig:
                    pending.append(sig)

        equity = pd.Series(equity_curve, name="equity").sort_index()
        bench = None
        if self.market is not None and not equity.empty:
            mc = self.market["m_close"].reindex(equity.index).ffill().dropna()
            if not mc.empty:
                bench = (mc / mc.iloc[0] * self.capital).rename("benchmark")
        return BacktestResult(
            equity=equity, trades=trades, signals=pd.DataFrame(signal_log), benchmark=bench, events=events,
            params={
                "strategies": {s.id: s.p for s in self.strategies},
                # rule strategies: the full spec, so the run is reproducible from the experiment log
                "specs": {s.id: s.spec_dict() for s in self.strategies if hasattr(s, "spec_dict")},
                "start": str(self.start),
                "end": str(self.end), "initial_capital": self.capital, "symbols": sorted(self.data),
                "open_positions_at_end": sorted(positions),
            },
        )
