"""End-to-end paper trading cycle with fake quotes (no network)."""

from datetime import datetime, timedelta

from market_view.broker.paper import PaperBroker
from market_view.config import IST
from market_view.data.sources.base import Quote
from market_view.journal import Journal
from market_view.models import Signal
from market_view.paper.trader import PaperTrader
from market_view.risk.killswitch import KillSwitch


def trader(tmp_path) -> PaperTrader:
    return PaperTrader(root=tmp_path, broker=PaperBroker(tmp_path / "broker.json", 500_000),
                       journal=Journal(tmp_path / "j.duckdb"), killswitch=KillSwitch(tmp_path / "ks.json"))


def q(sym, ltp, now, low=None, high=None, open_=None):
    return Quote(symbol=sym, ltp=ltp, low=low or ltp, high=high or ltp, open=open_ or ltp, time=now)


def queue_signal(t: PaperTrader, sym="TCS", price=1000.0, stop=970.0, target=1060.0, strategy="meanrev_v1"):
    s = Signal(strategy_id=strategy, symbol=sym, ref_price=price, stop=stop, target=target,
               bar_time=datetime(2026, 11, 4, 9, 15, tzinfo=IST), context={"turnover_cr": 500.0, "adv20": 1e7})
    t.st["pending_entries"] = [s.model_dump(mode="json")]
    t._save()


def test_entry_places_broker_side_stop_then_stop_exit(tmp_path):
    t = trader(tmp_path)
    now = datetime(2026, 11, 5, 9, 20, tzinfo=IST)
    queue_signal(t)
    out = t.open_job(now, {"TCS": q("TCS", 1001, now)})
    assert out["entries"], out
    pos = t.positions["TCS"]
    assert pos["protective_id"] in t.broker.protective()  # rule 4: broker-side stop exists
    assert t.reconcile() == []

    later = now + timedelta(minutes=30)
    res = t.monitor(later, {"TCS": q("TCS", 965, later)})
    assert res["fills"], res
    assert "TCS" not in t.positions
    trades = t.journal.query("SELECT * FROM trades")
    assert len(trades) == 1 and trades.iloc[0]["exit_reason"] == "stop"
    assert trades.iloc[0]["net_pnl"] < 0


def test_target_exit_via_oco(tmp_path):
    t = trader(tmp_path)
    now = datetime(2026, 11, 5, 9, 20, tzinfo=IST)
    queue_signal(t)
    t.open_job(now, {"TCS": q("TCS", 1000, now)})
    later = now + timedelta(hours=2)
    t.monitor(later, {"TCS": q("TCS", 1065, later)})
    trades = t.journal.query("SELECT exit_reason, net_pnl FROM trades")
    assert trades.iloc[0]["exit_reason"] == "target" and trades.iloc[0]["net_pnl"] > 0


def test_gap_below_stop_skips_entry(tmp_path):
    t = trader(tmp_path)
    now = datetime(2026, 11, 5, 9, 20, tzinfo=IST)
    queue_signal(t)
    out = t.open_job(now, {"TCS": q("TCS", 960, now)})
    assert not out["entries"] and "TCS" not in t.positions


def test_killswitch_blocks_new_entries(tmp_path):
    t = trader(tmp_path)
    t.killswitch.trigger("test", "unit")
    now = datetime(2026, 11, 5, 9, 20, tzinfo=IST)
    queue_signal(t)
    out = t.open_job(now, {"TCS": q("TCS", 1000, now)})
    assert not out["entries"]


def test_stale_quotes_trigger_killswitch(tmp_path):
    t = trader(tmp_path)
    now = datetime(2026, 11, 5, 9, 20, tzinfo=IST)
    queue_signal(t)
    t.open_job(now, {"TCS": q("TCS", 1000, now)})
    later = datetime(2026, 11, 5, 11, 0, tzinfo=IST)
    t.monitor(later, {"TCS": q("TCS", 1000, later - timedelta(hours=1))})
    assert t.killswitch.active


def test_scale_out_moves_stop_to_breakeven(tmp_path):
    t = trader(tmp_path)
    now = datetime(2026, 11, 5, 9, 20, tzinfo=IST)
    queue_signal(t, strategy="trend_v1", target=None)
    t.open_job(now, {"TCS": q("TCS", 1000, now)})
    entry = t.positions["TCS"]["entry_price"]
    level = entry + 1.5 * (entry - 970)
    later = now + timedelta(hours=1)
    res = t.monitor(later, {"TCS": q("TCS", level + 1, later)})
    assert res["scale_outs"]
    pos = t.positions["TCS"]
    assert pos["scaled_out"] and pos["stop"] >= entry
    assert pos["qty"] < pos["initial_qty"]
    assert t.reconcile() == []
