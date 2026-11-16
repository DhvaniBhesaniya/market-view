import os
import tempfile
from pathlib import Path

# isolate all data writes BEFORE market_view is imported
_TMP = Path(tempfile.mkdtemp(prefix="mv-test-"))
os.environ["MARKET_VIEW_DATA"] = str(_TMP)
os.environ["MARKET_VIEW_CUSTOM_STRATEGIES"] = str(_TMP / "custom_strategies")
os.environ["MARKET_VIEW_REPORTS"] = str(_TMP / "reports")
os.environ["LIVE_TRADING"] = "false"
os.environ.pop("UPSTOX_ACCESS_TOKEN", None)
os.environ.pop("TELEGRAM_BOT_TOKEN", None)

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
