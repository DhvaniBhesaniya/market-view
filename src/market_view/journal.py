"""Trade journal (DuckDB): every signal, decision, order, fill, trade, event and equity snapshot.

This is the dataset the weekly review and the Phase 6 AI journal analyst learn from.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

from market_view.config import DATA_DIR, IST
from market_view.models import Order, Signal, Trade

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (ts TIMESTAMPTZ, mode VARCHAR, signal_id VARCHAR, strategy_id VARCHAR, symbol VARCHAR,
  ref_price DOUBLE, stop DOUBLE, target DOUBLE, confidence DOUBLE, stage VARCHAR, approved BOOLEAN, qty INTEGER,
  decision VARCHAR, reasons VARCHAR, context VARCHAR);
CREATE TABLE IF NOT EXISTS orders (ts TIMESTAMPTZ, mode VARCHAR, client_order_id VARCHAR, broker_order_id VARCHAR,
  symbol VARCHAR, side VARCHAR, qty INTEGER, order_type VARCHAR, status VARCHAR, tag VARCHAR, strategy_id VARCHAR, note VARCHAR);
CREATE TABLE IF NOT EXISTS trades (closed_at TIMESTAMPTZ, mode VARCHAR, strategy_id VARCHAR, symbol VARCHAR,
  entry_time TIMESTAMPTZ, exit_time TIMESTAMPTZ, entry_price DOUBLE, exit_price DOUBLE, qty INTEGER, initial_stop DOUBLE,
  target DOUBLE, gross_pnl DOUBLE, charges DOUBLE, net_pnl DOUBLE, r_multiple DOUBLE, bars_held INTEGER, mae_pct DOUBLE,
  mfe_pct DOUBLE, exit_reason VARCHAR, reasons VARCHAR, context VARCHAR, review_note VARCHAR, rule_followed BOOLEAN);
CREATE TABLE IF NOT EXISTS events (ts TIMESTAMPTZ, mode VARCHAR, level VARCHAR, message VARCHAR);
CREATE TABLE IF NOT EXISTS equity (ts TIMESTAMPTZ, mode VARCHAR, equity DOUBLE, cash DOUBLE, open_positions INTEGER,
  drawdown_pct DOUBLE, day_pnl_pct DOUBLE);
"""


class Journal:
    def __init__(self, path: Path | None = None, mode: str = "paper") -> None:
        self.path = path or DATA_DIR / "journal.duckdb"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.mode = mode
        with self._conn() as c:
            c.execute(SCHEMA)

    def _conn(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self.path))

    @staticmethod
    def _now() -> datetime:
        return datetime.now(IST)

    def signal(self, sig: Signal, stage: str, approved: bool | None, qty: int = 0, decision: str = "",
               reasons: list[str] | None = None) -> None:
        with self._conn() as c:
            c.execute("INSERT INTO signals VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
                self._now(), self.mode, sig.id, sig.strategy_id, sig.symbol, sig.ref_price, sig.stop, sig.target,
                sig.confidence, stage, approved, qty, decision, "; ".join(reasons or sig.reasons),
                json.dumps(sig.context, default=str)])

    def order(self, o: Order, note: str | None = None) -> None:
        with self._conn() as c:
            c.execute("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", [
                self._now(), self.mode, o.client_order_id, o.broker_order_id, o.symbol, str(o.side), o.qty,
                str(o.order_type), str(o.status), o.tag, o.strategy_id, note])

    def trade(self, t: Trade) -> None:
        with self._conn() as c:
            c.execute("INSERT INTO trades VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
                self._now(), self.mode, t.strategy_id, t.symbol, t.entry_time, t.exit_time, t.entry_price,
                t.exit_price, t.qty, t.initial_stop, t.target, t.gross_pnl, t.charges, t.net_pnl, t.r_multiple,
                t.bars_held, t.mae_pct, t.mfe_pct, t.exit_reason, "; ".join(t.reasons),
                json.dumps(t.context, default=str), None, None])

    def event(self, level: str, message: str) -> None:
        with self._conn() as c:
            c.execute("INSERT INTO events VALUES (?,?,?,?)", [self._now(), self.mode, level, message])

    def equity(self, equity: float, cash: float, open_positions: int, drawdown_pct: float, day_pnl_pct: float) -> None:
        with self._conn() as c:
            c.execute("INSERT INTO equity VALUES (?,?,?,?,?,?,?)",
                      [self._now(), self.mode, equity, cash, open_positions, drawdown_pct, day_pnl_pct])

    def query(self, sql: str) -> pd.DataFrame:
        with self._conn() as c:
            return c.execute(sql).df()

    def review(self, rowid_entry_time: str, symbol: str, note: str, rule_followed: bool) -> None:
        """Weekly post-mortem: was it a GOOD trade (rules followed), regardless of profit?"""
        with self._conn() as c:
            c.execute("UPDATE trades SET review_note = ?, rule_followed = ? WHERE symbol = ? AND CAST(entry_time AS VARCHAR) LIKE ?",
                      [note, rule_followed, symbol, f"{rowid_entry_time}%"])
