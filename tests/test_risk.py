from datetime import datetime

import pytest

from market_view.config import IST, RiskConfig
from market_view.models import Signal
from market_view.risk.engine import OpenRisk, PortfolioState, RiskEngine, position_size
from market_view.risk.killswitch import KillSwitch


def sig(symbol="RELIANCE", price=1000.0, stop=972.0, target=None, **ctx) -> Signal:
    return Signal(strategy_id="trend_v1", symbol=symbol, ref_price=price, stop=stop, target=target,
                  bar_time=datetime(2026, 1, 5, tzinfo=IST), context=ctx)


def state(equity=500_000.0, **kw) -> PortfolioState:
    base = dict(equity=equity, cash=equity, peak_equity=equity, day_start_equity=equity, week_start_equity=equity)
    base.update(kw)
    return PortfolioState(**base)


def engine(**cfg) -> RiskEngine:
    return RiskEngine(cfg=RiskConfig(**cfg), sectors={"RELIANCE": "Energy", "ONGC": "Energy", "BPCL": "Energy",
                                                       "TCS": "IT"}, initial_capital=500_000)


def test_position_size_doc_example():
    # docs/05: Rs 5,00,000 x 0.25% = 1,250 / (1000-972=28) -> 44 shares
    assert position_size(500_000, 0.25, 1000, 972) == 44
    assert position_size(500_000, 0.25, 1000, 1000) == 0


def test_approves_normal_trade():
    d = engine().check(sig(), 1000, state())
    assert d.approved and d.qty == 44


def test_rejects_stop_above_price():
    d = engine().check(sig(stop=1010), 1000, state())
    assert not d.approved


def test_risk_ceiling_enforced_in_config():
    with pytest.raises(ValueError):
        RiskConfig(risk_per_trade_pct=1.0)


def test_max_positions_and_duplicates():
    pos = [OpenRisk(f"S{i}", "x", f"sec{i}", 1, 100, 95, 100) for i in range(5)]
    assert not engine().check(sig(), 1000, state(positions=pos)).approved
    held = [OpenRisk("RELIANCE", "x", "Energy", 10, 1000, 950, 1000)]
    assert not engine().check(sig(), 1000, state(positions=held)).approved


def test_sector_limit():
    held = [OpenRisk("ONGC", "x", "Energy", 1, 100, 99, 100), OpenRisk("BPCL", "x", "Energy", 1, 100, 99, 100)]
    d = engine().check(sig("RELIANCE"), 1000, state(positions=held))
    assert not d.approved and any("sector" in r for r in d.reasons)


def test_daily_loss_cap_blocks_entries():
    d = engine().check(sig(), 1000, state(equity=494_000, day_start_equity=500_000, peak_equity=500_000))
    assert not d.approved and any("daily loss" in r for r in d.reasons)


def test_killswitch_blocks():
    assert not engine().check(sig(), 1000, state(killswitch_active=True)).approved


def test_position_value_cap_resizes():
    # tight stop (Rs 10) -> 125 shares = Rs 1.25 lakh -> capped at 20% of equity = Rs 1,00,000 -> 100 shares
    d = engine().check(sig(stop=990), 1000, state())
    assert d.approved and d.qty == 100


def test_too_tight_stop_fails_cost_vs_edge():
    # Rs 1 stop: a 2R move is Rs 2/share, which barely covers charges -> not worth taking
    d = engine().check(sig(stop=999), 1000, state())
    assert not d.approved and any("costs" in r for r in d.reasons)


def test_illiquid_rejected():
    assert not engine().check(sig(turnover_cr=5.0), 1000, state()).approved


def test_cost_vs_edge_rejects_tiny_targets():
    d = engine().check(sig(stop=999.5, target=1000.5), 1000, state())
    assert not d.approved


def test_strategy_breaker_disables_after_losses():
    e = engine(max_consecutive_losses=3)
    st = state()
    for _ in range(3):
        e.on_trade_closed(st, "trend_v1", -1000)
    assert "trend_v1" in st.disabled_strategies
    assert not e.check(sig(), 1000, st).approved


def test_killswitch_reset_requires_note(tmp_path):
    ks = KillSwitch(tmp_path / "ks.json")
    ks.trigger("test", "unit")
    assert ks.active
    with pytest.raises(ValueError):
        ks.reset("ok")
    ks.reset("reviewed logs, data feed restored")
    assert not ks.active
