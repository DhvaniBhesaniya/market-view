"""Strategy registry: hand-written strategies (code) + custom rule strategies (config/custom_strategies/)."""

from __future__ import annotations

from market_view.strategies.base import Manage, PositionView, Strategy
from market_view.strategies.breakout import BreakoutV1
from market_view.strategies.meanrev import MeanReversionV1
from market_view.strategies.trend import TrendPullbackV1

REGISTRY: dict[str, type[Strategy]] = {
    cls.name + f"_v{cls.version}": cls for cls in (TrendPullbackV1, BreakoutV1, MeanReversionV1)
}


def all_classes() -> dict[str, type[Strategy]]:
    """Built-in strategies plus every saved rule strategy version (read fresh from disk)."""
    from market_view.strategies.rules import custom_classes

    return {**REGISTRY, **custom_classes()}


def get_class(strategy_id: str) -> type[Strategy]:
    if strategy_id in REGISTRY:
        return REGISTRY[strategy_id]
    classes = all_classes()
    if strategy_id not in classes:
        raise KeyError(f"unknown strategy {strategy_id!r}; known: {sorted(classes)}")
    return classes[strategy_id]


def make(strategy_id: str, **overrides) -> Strategy:
    cls = get_class(strategy_id)
    from market_view.config import get_settings

    params = {**get_settings().strategies.params.get(strategy_id, {}), **overrides}
    return cls(**params)


def enabled() -> list[Strategy]:
    from market_view.config import get_settings

    return [make(s) for s in get_settings().strategies.enabled]


__all__ = ["REGISTRY", "Manage", "PositionView", "Strategy", "all_classes", "enabled", "get_class", "make"]
