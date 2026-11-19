"""Paper trader: the daily swing-trading loop on live data with a simulated broker.

Jobs (IST, trading days — see config/paper.yaml):
  open_job  ~09:20  execute exits flagged last night, then new entries (final risk check at the
                    real opening price; skip if it gapped below the stop); place broker-side stops
  monitor   every N min  feed quotes to the broker's resting stops/targets, scale-out, kill-switch checks
  eod       ~15:45  update daily candles, manage positions (trail stops / exit flags), mark to
                    market, generate tomorrow's signals (pre-checked by the risk engine)

The strategy and risk code are the SAME objects the backtester uses — that is what makes paper
results comparable to backtest results.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from market_view import calendar as cal
from market_view.broker.paper import PaperBroker
from market_view.config import DATA_DIR, IST, get_settings
from market_view.costs import CostModel
from market_view.data import store
from market_view.data.sources import DataSource, Quote, get_source
from market_view.execution.engine import EntryBlocked, ExecutionEngine
from market_view.journal import Journal
from market_view.market_context.regime import prepare_market
from market_view.models import Order, OrderStatus, Side, Signal, Trade
from market_view.notify import notify
from market_view.risk.engine import OpenRisk, PortfolioState, RiskEngine
from market_view.risk.killswitch import KillSwitch
from market_view.strategies import enabled, make
from market_view.strategies.base import PositionView


class PaperTrader:
    def __init__(self, root: Path | None = None, broker: PaperBroker | None = None, journal: Journal | None = None,
                 killswitch: KillSwitch | None = None, history_source: DataSource | None = None,
                 live_source: DataSource | None = None) -> None:
        s = get_settings()
        self.settings = s
        self.cfg = s.paper
        self.dir = root or DATA_DIR / "paper"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.costs = CostModel()
        self.broker = broker or PaperBroker(self.dir / "broker.json", self.cfg.initial_capital, self.costs, self.cfg.product)
        self.journal = journal or Journal(mode="paper")
        self.killswitch = killswitch or KillSwitch()
        self.exec = ExecutionEngine(self.broker, self.journal, self.killswitch)
        self.risk = RiskEngine(costs=self.costs, initial_capital=self.cfg.initial_capital)
        self._history_source = history_source
        self._live_source = live_source
        self.state_path = self.dir / "trader.json"
        if self.state_path.exists():
            self.st = json.loads(self.state_path.read_text(encoding="utf-8"))
        else:
            cap = self.cfg.initial_capital
            self.st = {
                "created": datetime.now(IST).isoformat(), "initial_capital": cap, "peak_equity": cap,
                "day": {"date": None, "equity": cap}, "week": {"key": None, "equity": cap},
                "positions": {}, "pending_entries": [], "last_eod": None, "last_open": None, "last_monitor": None,
                "strategy": {"pnl": {}, "peak": {}, "consecutive_losses": {}, "disabled": {}},
            }
            self._save()

    # ------------------------------------------------------------------ plumbing
    def _save(self) -> None:
        pending = self.state_path.with_suffix(".tmp")
        pending.write_text(json.dumps(self.st, indent=2, default=str), encoding="utf-8")
        pending.replace(self.state_path)

    def _fresh_quotes(self, quotes: dict[str, Quote], symbols: list[str], now: datetime) -> tuple[dict[str, Quote], list[str]]:
        fresh, issues = {}, []
        for sym in symbols:
            q = quotes.get(sym)
            if q is None:
                issues.append(f"no quote for {sym}")
                continue
            age = (now - q.time).total_seconds() if q.time.tzinfo else float("inf")
            if not math.isfinite(q.ltp) or q.ltp <= 0 or not -5 <= age <= self.cfg.stale_data_seconds:
                issues.append(f"stale/invalid quote for {sym}: {age:.0f}s old")
                continue
            fresh[sym] = q
        if issues:
            self.killswitch.trigger("; ".join(issues), "quote validation")
        return fresh, issues

    def history_source(self) -> DataSource:
        if self._history_source is None:
            self._history_source = get_source(self.cfg.history_source)
        return self._history_source

    def live_source(self) -> DataSource:
        if self._live_source is None:
            self._live_source = get_source(self.cfg.live_data_source)
        return self._live_source

    @property
    def positions(self) -> dict[str, dict]:
        return self.st["positions"]

    def equity(self, quotes: dict[str, Quote] | None = None) -> float:
        quotes = quotes or {}
        value = sum(p["qty"] * (quotes[s].ltp if s in quotes else p["last_price"]) for s, p in self.positions.items())
        return self.broker.funds().cash + value

    def _roll_period(self, today: date, quotes: dict[str, Quote] | None = None) -> None:
        # Reset against the last saved mark, before incorporating today's opening gap.
        eq = self.equity()
        if self.st["day"]["date"] != today.isoformat():
            self.st["day"] = {"date": today.isoformat(), "equity": eq}
        iso = today.isocalendar()
        wk = f"{iso.year}-{iso.week:02d}"
        if self.st["week"]["key"] != wk:
            self.st["week"] = {"key": wk, "equity": eq}

    def _state(self, quotes: dict[str, Quote] | None = None, include_pending: bool = True) -> PortfolioState:
        quotes = quotes or {}
        eq = self.equity(quotes)
        sst = self.st["strategy"]
        return PortfolioState(
            equity=eq, cash=self.broker.funds().cash, peak_equity=max(self.st["peak_equity"], eq),
            day_start_equity=self.st["day"]["equity"], week_start_equity=self.st["week"]["equity"],
            positions=[OpenRisk(s, p["strategy_id"], self.risk.sector(s), p["qty"], p["entry_price"], p["stop"],
                                quotes[s].ltp if s in quotes else p["last_price"]) for s, p in self.positions.items()],
            pending_symbols={d["symbol"] for d in self.st["pending_entries"]} if include_pending else set(),
            strategy_peak=dict(sst["peak"]), strategy_pnl=dict(sst["pnl"]),
            consecutive_losses=dict(sst["consecutive_losses"]), disabled_strategies=dict(sst["disabled"]),
            killswitch_active=self.killswitch.active,
        )

    def _fill_for(self, client_order_id: str) -> dict | None:
        for f in reversed(self.broker.s["fills"]):
            if f["client_order_id"] == client_order_id:
                return f
        return None

    # ------------------------------------------------------------------ exits
    def _record_exit(self, symbol: str, price: float, qty: int, charges: float, reason: str, when: datetime) -> Trade | None:
        pos = self.positions[symbol]
        pos["qty"] -= qty
        pos["exit_qty"] += qty
        pos["exit_value"] += price * qty
        pos["charges"] += charges
        if pos["qty"] > 0:
            self.journal.event("INFO", f"partial exit {symbol} {qty} @ {price:.2f} ({reason})")
            return None
        gross = pos["exit_value"] - pos["entry_price"] * pos["initial_qty"]
        net = gross - pos["charges"]
        r_den = (pos["entry_price"] - pos["initial_stop"]) * pos["initial_qty"]
        trade = Trade(
            strategy_id=pos["strategy_id"], symbol=symbol, entry_time=pos["entry_time"], exit_time=when,
            entry_price=pos["entry_price"], exit_price=pos["exit_value"] / pos["exit_qty"], qty=pos["initial_qty"],
            initial_stop=pos["initial_stop"], target=pos["target"], gross_pnl=gross, charges=pos["charges"],
            net_pnl=net, r_multiple=net / r_den if r_den > 0 else 0.0, bars_held=pos["bars_held"],
            mae_pct=(min(pos["lowest_low"], price) / pos["entry_price"] - 1) * 100,
            mfe_pct=(max(pos["highest_high"], price) / pos["entry_price"] - 1) * 100,
            exit_reason=reason, reasons=pos["signal"].get("reasons", []), context=pos["signal"].get("context", {}),
        )
        self.journal.trade(trade)
        del self.positions[symbol]
        state = self._state()
        events = self.risk.on_trade_closed(state, trade.strategy_id, net)
        sst = self.st["strategy"]
        sst["pnl"], sst["peak"] = state.strategy_pnl, state.strategy_peak
        sst["consecutive_losses"], sst["disabled"] = state.consecutive_losses, state.disabled_strategies
        msg = f"CLOSED {symbol} {trade.strategy_id}: {net:+,.0f} Rs ({trade.r_multiple:+.2f}R) - {reason}"
        notify(msg)
        for e in events:
            notify(e, "WARNING")
            self.journal.event("WARNING", e)
        return trade

    def _exit_market(self, symbol: str, reason: str, when: datetime) -> None:
        pos = self.positions[symbol]
        if pos.get("protective_id"):
            self.broker.cancel_protective(pos["protective_id"])
        order = Order(symbol=symbol, side=Side.SELL, qty=pos["qty"], tag="exit", strategy_id=pos["strategy_id"])
        self.exec.submit(order)
        fill = self._fill_for(order.client_order_id)
        if order.status == OrderStatus.COMPLETE and fill:
            self._record_exit(symbol, fill["price"], fill["qty"], fill["charges"], reason, when)
        else:
            # could not exit: restore the broker-side stop so the position is never naked
            pos["protective_id"] = self.broker.place_protective(symbol, pos["qty"], pos["stop"], pos["target"])
            notify(f"EXIT FAILED {symbol}: stop restored", "ERROR")

    # ------------------------------------------------------------------ jobs
    def eod(self, today: date | None = None, update_data: bool = True,
            data: dict[str, pd.DataFrame] | None = None, market: pd.DataFrame | None = None) -> dict:
        today = today or cal.now_ist().date()
        summary: dict = {"date": today.isoformat(), "new_signals": [], "rejected": [], "managed": [], "warnings": []}
        if not cal.is_trading_day(today):  # no new bar today: keep pending signals for the next session
            summary["warnings"].append(f"{today} is not a trading day: nothing to do (pending signals kept)")
            return summary
        if data is None:
            src = self.history_source()
            start = today - timedelta(days=500)
            symbols = list(self.settings.universe.indices) + self.settings.universe.all_symbols(include_former=False)
            if update_data:
                for sym in symbols:
                    try:
                        store.save(src.history(sym, "1d", today - timedelta(days=10), today), src.name, "1d", sym)
                    except Exception as e:
                        summary["warnings"].append(f"download {sym}: {e}")
            data = store.load_many(self.settings.universe.all_symbols(include_former=False), "1d", src.name, start, today)
            nifty = store.load(self.settings.backtest.benchmark, "1d", src.name, start, today)
            vix = store.load(self.settings.backtest.volatility_index, "1d", src.name, start, today)
            market = prepare_market(nifty, vix) if not nifty.empty else None
        self._roll_period(today)
        strategies = enabled()
        prepared = {s.id: {sym: s.prepare(df, market) for sym, df in data.items()} for s in strategies}

        # 1) manage open positions with today's completed bar
        for sym, pos in list(self.positions.items()):
            df = data.get(sym)
            if df is None or df.empty or df.index[-1].date() != today:
                summary["warnings"].append(f"{sym}: no bar for {today} (stale data?)")
                continue
            last_ts = df.index[-1]
            if pos.get("last_bar_date") == today.isoformat():
                continue
            _, h, low, c = (float(x) for x in df.loc[last_ts, ["open", "high", "low", "close"]])
            pos["highest_high"] = max(pos["highest_high"], h)
            pos["lowest_low"] = min(pos["lowest_low"], low)
            pos["bars_held"] += 1
            pos["last_price"] = c
            pos["last_bar_date"] = today.isoformat()
            strat = make(pos["strategy_id"])
            prep = prepared.get(strat.id, {}).get(sym)
            if prep is None:
                prep = strat.prepare(df, market)
            view = PositionView(symbol=sym, qty=pos["qty"], entry_price=pos["entry_price"],
                                entry_time=datetime.fromisoformat(str(pos["entry_time"])),
                                initial_stop=pos["initial_stop"], stop=pos["stop"], target=pos["target"],
                                bars_held=pos["bars_held"], highest_high=pos["highest_high"], scaled_out=pos["scaled_out"])
            m = strat.manage(view, prep.loc[last_ts])
            if m.new_stop is not None and m.new_stop > pos["stop"]:
                pos["stop"] = round(m.new_stop, 2)
                if pos.get("protective_id"):
                    self.broker.modify_protective(pos["protective_id"], stop=pos["stop"],
                                                  at=datetime.combine(today, datetime.min.time(), IST))
                summary["managed"].append(f"{sym}: stop raised to {pos['stop']:.2f} ({m.reason})")
            if m.exit_next_open:
                pos["exit_next_open"] = m.reason
                summary["managed"].append(f"{sym}: exit at next open ({m.reason})")

        # 2) mark to market + breakers
        eq = self.equity()
        self.st["peak_equity"] = max(self.st["peak_equity"], eq)
        state = self._state()
        self.journal.equity(eq, state.cash, len(self.positions), state.drawdown_pct, state.day_pnl_pct)
        breaker = self.risk.portfolio_breaker(state)
        if breaker and "drawdown" in breaker:
            self.killswitch.trigger(breaker, "portfolio breaker")
            notify(f"KILL SWITCH: {breaker}", "CRITICAL")

        # 3) tomorrow's signals (expire if not executed at the next open)
        self.st["pending_entries"] = []
        state = self._state()
        for strat in strategies:
            for sym, prep in prepared[strat.id].items():
                if prep.empty or prep.index[-1].date() != today:
                    continue
                sig = strat.signal_at(prep, prep.index[-1], sym)
                if sig is None:
                    continue
                if sym in self.positions or sym in state.pending_symbols:
                    self.journal.signal(sig, "eod_precheck", False, decision="duplicate", reasons=["already held/pending"])
                    continue
                dec = self.risk.check(sig, sig.ref_price, state)
                self.journal.signal(sig, "eod_precheck", dec.approved, dec.qty, reasons=dec.reasons or sig.reasons)
                if dec.approved:
                    self.st["pending_entries"].append(sig.model_dump(mode="json"))
                    state.pending_symbols.add(sym)
                    summary["new_signals"].append(f"{sig.strategy_id} {sym} ref {sig.ref_price:.2f} stop {sig.stop:.2f} ~{dec.qty} sh")
                else:
                    summary["rejected"].append(f"{sig.strategy_id} {sym}: {'; '.join(dec.reasons)}")

        self.st["last_eod"] = today.isoformat()
        self._save()
        summary.update(equity=round(eq, 2), drawdown_pct=round(state.drawdown_pct, 2), open_positions=len(self.positions))
        notify(f"EOD {today}: equity Rs {eq:,.0f}, {len(self.positions)} open, {len(summary['new_signals'])} signals for tomorrow")
        return summary

    def open_job(self, now: datetime | None = None, quotes: dict[str, Quote] | None = None,
                 entry_permission: Callable[[], bool] | None = None) -> dict:
        now = now or cal.now_ist()
        summary: dict = {"time": now.isoformat(), "exits": [], "entries": [], "skipped": []}
        # quotes outside the session are stale (yesterday's close / a weekend): never trade on them
        if not cal.is_trading_day(now.date()):
            summary["skipped"].append(f"{now.date()} is not a trading day: pending signals kept")
            return summary
        if not cal.is_market_open(now):
            summary["skipped"].append(f"market closed at {now:%H:%M} IST: pending signals kept")
            return summary
        if self.st["last_open"] == now.date().isoformat():
            summary["skipped"].append("open job already completed today")
            return summary
        self.reconcile()  # unresolved positions or missing protection veto every new entry
        exit_syms = [s for s, p in self.positions.items() if p.get("exit_next_open")]
        entry_syms = [d["symbol"] for d in self.st["pending_entries"]]
        quote_syms = sorted(set(self.positions) | set(entry_syms))
        if quotes is None:
            quotes = self.live_source().quotes(quote_syms) if quote_syms else {}
        quotes, issues = self._fresh_quotes(quotes, quote_syms, now)
        summary["skipped"].extend(issues)
        self.broker.set_quotes(quotes)
        self._roll_period(now.date(), quotes)

        for sym in exit_syms:  # exits first: frees cash and risk
            if sym not in quotes:
                summary["skipped"].append(f"exit {sym}: no quote")
                continue
            self._exit_market(sym, self.positions[sym]["exit_next_open"], now)
            if sym not in self.positions:
                summary["exits"].append(sym)
            else:
                summary["skipped"].append(f"exit {sym}: did not complete; inspect protection and journal")

        for d in sorted(self.st["pending_entries"], key=lambda x: -x["confidence"]):
            sig = Signal(**d)
            if entry_permission is not None and not entry_permission():
                self.journal.signal(sig, "open_final", False, decision="paused", reasons=["paper entries paused in the application"])
                summary["skipped"].append(f"{sig.symbol}: entries paused")
                continue
            next_day = sig.bar_time.astimezone(IST).date() + timedelta(days=1)
            while not cal.is_trading_day(next_day):
                next_day += timedelta(days=1)
            if next_day != now.date():
                self.journal.signal(sig, "open_final", False, decision="expired", reasons=["signal is only valid for the next trading session"])
                summary["skipped"].append(f"{sig.symbol}: expired signal")
                continue
            q = quotes.get(sig.symbol)
            if q is None:
                self.journal.signal(sig, "open_final", False, decision="no quote", reasons=["no quote at open"])
                summary["skipped"].append(f"{sig.symbol}: no quote")
                continue
            if q.ltp <= sig.stop:
                self.journal.signal(sig, "open_final", False, decision="gap", reasons=[f"opened {q.ltp:.2f} <= stop {sig.stop:.2f}"])
                summary["skipped"].append(f"{sig.symbol}: gapped below stop")
                continue
            # pending entries are being executed now, so they are not "duplicates" of themselves
            dec = self.risk.check(sig, self.costs.fill_price(Side.BUY, q.ltp), self._state(quotes, include_pending=False))
            self.journal.signal(sig, "open_final", dec.approved, dec.qty, reasons=dec.reasons)
            if not dec.approved:
                summary["skipped"].append(f"{sig.symbol}: {'; '.join(dec.reasons)}")
                continue
            order = Order(symbol=sig.symbol, side=Side.BUY, qty=dec.qty, tag="entry",
                          strategy_id=sig.strategy_id, signal_id=sig.id)
            try:
                self.exec.submit(order)
            except EntryBlocked as e:
                summary["skipped"].append(str(e))
                break
            fill = self._fill_for(order.client_order_id)
            if order.status != OrderStatus.COMPLETE or not fill:
                summary["skipped"].append(f"{sig.symbol}: order {order.status}")
                continue
            self.positions[sig.symbol] = {
                "strategy_id": sig.strategy_id, "qty": fill["qty"], "initial_qty": fill["qty"],
                "entry_price": fill["price"], "entry_time": now.isoformat(), "initial_stop": sig.stop, "stop": sig.stop,
                "target": sig.target, "highest_high": fill["price"], "lowest_low": fill["price"], "bars_held": 0,
                "scaled_out": False, "exit_qty": 0, "exit_value": 0.0, "charges": fill["charges"],
                "exit_next_open": None, "protective_id": None, "last_price": fill["price"],
                "last_bar_date": None, "signal": d,
            }
            self._save()  # protection failures must leave a recoverable position record
            try:
                pid = self.broker.place_protective(sig.symbol, fill["qty"], sig.stop, sig.target)
                self.positions[sig.symbol]["protective_id"] = pid
            except Exception:
                self.killswitch.trigger(f"Protective stop failed for {sig.symbol}", "entry protection")
                self.journal.event("ERROR", f"Protective stop failed for {sig.symbol}; emergency paper exit requested")
                try:
                    self._exit_market(sig.symbol, "protective placement failure", now)
                finally:
                    self._save()
                summary["skipped"].append(f"{sig.symbol}: protective placement failed; emergency exit requested")
                continue
            summary["entries"].append(f"{sig.symbol} {fill['qty']} @ {fill['price']:.2f} stop {sig.stop:.2f}")
            notify(f"ENTRY {sig.strategy_id} {sig.symbol} {fill['qty']} @ {fill['price']:.2f}, broker-side stop {sig.stop:.2f}")
        self.st["pending_entries"] = []
        self.st["last_open"] = now.date().isoformat()
        self._save()
        return summary

    def monitor(self, now: datetime | None = None, quotes: dict[str, Quote] | None = None) -> dict:
        now = now or cal.now_ist()
        summary: dict = {"time": now.isoformat(), "fills": [], "scale_outs": [], "alerts": []}
        if not self.positions:
            self.st["last_monitor"] = now.isoformat()
            self._save()
            return summary
        if quotes is None:
            quotes = self.live_source().quotes(sorted(self.positions))
        quotes, issues = self._fresh_quotes(quotes, sorted(self.positions), now)
        summary["alerts"].extend(issues)
        self._roll_period(now.date(), quotes)

        # broker-side protective orders
        for pid, kind, fill in self.broker.on_quotes(quotes):
            sym = fill.symbol
            pos = self.positions.get(sym)
            if pos is None or pos.get("protective_id") != pid:
                continue
            reason = kind if kind == "target" else ("stop" if pos["stop"] < pos["entry_price"] else "trailing stop")
            self._record_exit(sym, fill.price, fill.qty, fill.charges, reason, now)
            summary["fills"].append(f"{sym} {kind} @ {fill.price:.2f}")

        # strategy scale-out (trader-managed partial profit booking; the stop stays broker-side)
        for sym, pos in list(self.positions.items()):
            q = quotes.get(sym)
            if q is None:
                continue
            pos["last_price"] = q.ltp
            strat = make(pos["strategy_id"])
            if not strat.scale_out_r or pos["scaled_out"]:
                continue
            level = pos["entry_price"] + strat.scale_out_r * (pos["entry_price"] - pos["initial_stop"])
            if q.ltp >= level:
                qty = math.floor(pos["qty"] * strat.scale_out_fraction)
                if qty >= 1:
                    order = Order(symbol=sym, side=Side.SELL, qty=qty, tag="exit", strategy_id=pos["strategy_id"])
                    self.exec.submit(order)
                    fill = self._fill_for(order.client_order_id)
                    if order.status == OrderStatus.COMPLETE and fill:
                        self._record_exit(sym, fill["price"], fill["qty"], fill["charges"], f"scale-out {strat.scale_out_r}R", now)
                pos["scaled_out"] = True
                pos["stop"] = max(pos["stop"], pos["entry_price"])
                if pos.get("protective_id") and sym in self.positions:
                    self.broker.modify_protective(pos["protective_id"], stop=pos["stop"], qty=pos["qty"], at=now)
                summary["scale_outs"].append(f"{sym}: sold {qty}, stop -> breakeven {pos['stop']:.2f}")

        state = self._state(quotes)
        self.st["peak_equity"] = max(self.st["peak_equity"], state.equity)
        breaker = self.risk.portfolio_breaker(state)
        if breaker and "drawdown" in breaker:
            self.killswitch.trigger(breaker, "portfolio breaker")
            summary["alerts"].append(breaker)
        if state.day_pnl_pct <= -self.settings.risk.daily_loss_cap_pct:
            reason = f"daily loss {state.day_pnl_pct:.2f}% hit cap {self.settings.risk.daily_loss_cap_pct}%"
            self.killswitch.trigger(reason, "daily loss cap")
            summary["alerts"].append(reason)
        for a in summary["alerts"]:
            notify(a, "WARNING")
            self.journal.event("WARNING", a)
        self.st["last_monitor"] = now.isoformat()
        self._save()
        return summary

    # ------------------------------------------------------------------ checks & views
    def reconcile(self) -> list[str]:
        """Broker positions must equal our records. Any mismatch -> kill switch."""
        broker_pos = {p.symbol: p.qty for p in self.broker.positions()}
        ours = {s: p["qty"] for s, p in self.positions.items()}
        issues = [f"{s}: broker {broker_pos.get(s, 0)} vs ours {ours.get(s, 0)}"
                  for s in sorted(set(broker_pos) | set(ours)) if broker_pos.get(s, 0) != ours.get(s, 0)]
        for s, p in self.positions.items():
            if not p.get("protective_id") or p["protective_id"] not in self.broker.protective():
                issues.append(f"{s}: no broker-side stop")
        if issues:
            self.killswitch.trigger("reconciliation mismatch: " + "; ".join(issues), "reconcile")
            notify("RECONCILIATION MISMATCH: " + "; ".join(issues), "CRITICAL")
        return issues

    def status(self) -> dict:
        state = self._state()
        return {
            "equity": round(state.equity, 2), "cash": round(state.cash, 2),
            "return_pct": round((state.equity / self.st["initial_capital"] - 1) * 100, 2),
            "drawdown_pct": round(state.drawdown_pct, 2), "open_risk": round(sum(p.risk for p in state.positions), 2),
            "positions": {s: {k: p[k] for k in ("strategy_id", "qty", "entry_price", "stop", "target", "last_price",
                                                "bars_held", "scaled_out", "exit_next_open")}
                          for s, p in self.positions.items()},
            "pending_entries": [f"{d['strategy_id']} {d['symbol']}" for d in self.st["pending_entries"]],
            "disabled_strategies": self.st["strategy"]["disabled"],
            "killswitch": self.killswitch.status().get("active"),
            "last_eod": self.st["last_eod"], "last_open": self.st["last_open"], "last_monitor": self.st["last_monitor"],
        }
