import os
import tempfile
from pathlib import Path

# isolate all data writes BEFORE market_view is imported
_TMP = Path(tempfile.mkdtemp(prefix="mv-test-"))
os.environ["MARKET_VIEW_DATA"] = str(_TMP)
os.environ["MARKET_VIEW_CUSTOM_STRATEGIES"] = str(_TMP / "custom_strategies")
os.environ["MARKET_VIEW_REPORTS"] = str(_TMP / "reports")
os.environ["LIVE_TRADING"] = "false"
# Set to "" (not popped): load_dotenv() never overrides an existing key, so the real .env stays out of tests.
for _secret in ("UPSTOX_ACCESS_TOKEN", "UPSTOX_API_KEY", "UPSTOX_API_SECRET", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
                "GROWW_API_KEY", "GROWW_API_SECRET", "GROWW_TOTP_SECRET", "ANTHROPIC_API_KEY"):
    os.environ[_secret] = ""

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from market_view.config import IST  # noqa: E402


def make_df(bars: list[tuple[float, float, float, float]], start: str = "2024-01-01", volume: int = 1_000_000) -> pd.DataFrame:
    """bars: list of (open, high, low, close), one per business day, stamped 09:15 IST."""
    days = pd.bdate_range(start, periods=len(bars))
    idx = pd.DatetimeIndex([pd.Timestamp(d.date(), tz=IST) + pd.Timedelta(hours=9, minutes=15) for d in days], name="ts")
    df = pd.DataFrame(bars, columns=["open", "high", "low", "close"], index=idx)
    df["volume"] = volume
    return df


def random_walk(n: int = 600, seed: int = 1, start_price: float = 1000.0, start: str = "2018-01-01") -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = start_price * np.exp(np.cumsum(rng.normal(0.0004, 0.015, n)))
    open_ = np.r_[start_price, close[:-1]] * (1 + rng.normal(0, 0.003, n))
    high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.01, n))
    low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.01, n))
    df = make_df(list(zip(open_, high, low, close, strict=True)), start)
    df["volume"] = rng.integers(500_000, 3_000_000, n)
    return df


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture(autouse=True)
def _pin_data_source(monkeypatch):
    """Tests are written against yfinance-keyed fixtures; don't depend on config/backtest.yaml's live choice."""
    from market_view.config import get_settings

    monkeypatch.setattr(get_settings().backtest, "data_source", "yfinance")
