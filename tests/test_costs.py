import pytest

from market_view.costs import CostModel
from market_view.models import Side


def test_delivery_buy_charges_hand_calculated():
    # Rs 1,00,000 delivery buy:
    # brokerage min(20, 0.1% = 100) = 20; STT 0.1% = 100; exchange 0.00307% = 3.07; SEBI 0.0001% = 0.10
    # stamp 0.015% = 15; GST 18% of (20 + 3.07 + 0.10) = 4.1706  -> 142.3406
    b = CostModel().breakdown(Side.BUY, 100_000, "CNC")
    assert b.brokerage == pytest.approx(20)
    assert b.stt == pytest.approx(100)
    assert b.stamp == pytest.approx(15)
    assert b.total == pytest.approx(142.3406, abs=1e-3)


def test_delivery_sell_has_dp_no_stamp():
    b = CostModel().breakdown(Side.SELL, 100_000, "CNC")
    assert b.stamp == 0
    assert b.dp == pytest.approx(20)
    assert b.total == pytest.approx(147.3406, abs=1e-3)


def test_intraday_much_cheaper_stt():
    c = CostModel()
    assert c.charges(Side.SELL, 100_000, "MIS") < c.charges(Side.SELL, 100_000, "CNC") / 2


def test_small_order_brokerage_is_percentage():
    # Rs 5,000 order: 0.1% = 5 < 20 flat
    assert CostModel().breakdown(Side.BUY, 5_000).brokerage == pytest.approx(5)


def test_slippage_always_worse():
    c = CostModel()
    assert c.fill_price(Side.BUY, 100) > 100
    assert c.fill_price(Side.SELL, 100) < 100


def test_round_trip_about_quarter_percent():
    rt = CostModel().round_trip(1000, 1000, 100)  # Rs 1 lakh each side
    assert 0.25 <= rt / 100_000 * 100 <= 0.32
