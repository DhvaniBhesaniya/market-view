import os

import pytest

from market_view.broker.paper import PaperBroker
from market_view.broker.upstox import UpstoxBroker
from market_view.config import LiveTradingDisabled, live_trading_enabled
from market_view.data.sources.base import Quote
from market_view.execution.engine import (
    EntryBlocked,
    ExecutionEngine,
    IllegalTransition,
    transition,
)
from market_view.journal import Journal
from market_view.models import Order, OrderStatus, Side
from market_view.risk.killswitch import KillSwitch


def test_live_trading_needs_both_switches(monkeypatch):
    monkeypatch.setenv("LIVE_TRADING", "false")
    assert not live_trading_enabled(True)
    monkeypatch.setenv("LIVE_TRADING", "true")
    assert not live_trading_enabled(False)
    assert live_trading_enabled(True)
    monkeypatch.setenv("LIVE_TRADING", "false")


def test_upstox_broker_orders_locked():
    with pytest.raises(LiveTradingDisabled):
        UpstoxBroker(live_flag=False).place_order(Order(symbol="TCS", side=Side.BUY, qty=1))


def test_execution_engine_refuses_live_broker_without_switches():
    assert os.environ.get("LIVE_TRADING") == "false"
    with pytest.raises(LiveTradingDisabled):
        ExecutionEngine(UpstoxBroker(), journal=None, killswitch=None, live_flag=True)


def test_illegal_transition():
    o = Order(symbol="TCS", side=Side.BUY, qty=1)
    with pytest.raises(IllegalTransition):
        transition(o, OrderStatus.COMPLETE)  # NEW cannot jump to COMPLETE


def _engine(tmp_path, ks=None):
    from datetime import datetime

    from market_view.config import IST

    broker = PaperBroker(tmp_path / "b.json", 100_000)
    broker.set_quotes({"TCS": Quote(symbol="TCS", ltp=1000, time=datetime.now(IST))})
    return broker, ExecutionEngine(broker, Journal(tmp_path / "j.duckdb"), ks or KillSwitch(tmp_path / "ks.json"))


def test_paper_fill_and_no_short_selling(tmp_path):
    broker, ex = _engine(tmp_path)
    o = ex.submit(Order(symbol="TCS", side=Side.BUY, qty=10, tag="entry"))
    assert o.status == OrderStatus.COMPLETE
    assert broker.positions()[0].qty == 10
    o2 = ex.submit(Order(symbol="TCS", side=Side.SELL, qty=20, tag="exit"))
    assert o2.status == OrderStatus.REJECTED_BROKER


def test_killswitch_blocks_entries_but_not_exits(tmp_path):
    ks = KillSwitch(tmp_path / "ks.json")
    broker, ex = _engine(tmp_path, ks)
    ex.submit(Order(symbol="TCS", side=Side.BUY, qty=5, tag="entry"))
    ks.trigger("test", "unit")
    with pytest.raises(EntryBlocked):
        ex.submit(Order(symbol="TCS", side=Side.BUY, qty=5, tag="entry"))
    assert ex.submit(Order(symbol="TCS", side=Side.SELL, qty=5, tag="exit")).status == OrderStatus.COMPLETE


def test_strategies_never_import_broker_or_execution():
    """CLAUDE.md rule 3: strategies emit Signals only."""
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "src" / "market_view" / "strategies"
    for f in src.glob("*.py"):
        text = f.read_text(encoding="utf-8")
        assert "market_view.broker" not in text and "market_view.execution" not in text, f.name
