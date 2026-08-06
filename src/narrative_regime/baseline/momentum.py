from __future__ import annotations

import pandas as pd

from narrative_regime.baseline.engine import (
    BacktestResult,
    close_panel,
    run_monthly_ranked_backtest,
)

MomentumResult = BacktestResult


def run_momentum_baseline(
    prices: pd.DataFrame,
    *,
    lookback: int = 60,
    top_n: int = 3,
    cost_bps: float = 10.0,
) -> MomentumResult:
    """Run the frozen monthly momentum baseline on adjusted closing prices.

    Signals use each calendar month's final observed close. Target weights become
    active on the next panel date. Consequently, that date's close-to-close return
    is an explicit daily-data approximation to next-session execution.
    """
    if lookback < 1:
        raise ValueError("lookback must be at least 1")
    if top_n < 1:
        raise ValueError("top_n must be at least 1")
    if cost_bps < 0:
        raise ValueError("cost_bps must not be negative")

    close = close_panel(prices)
    if len(close.index) <= lookback:
        raise ValueError("price history is shorter than the momentum lookback")

    momentum = close.div(close.shift(lookback)).sub(1.0)
    return run_monthly_ranked_backtest(
        prices,
        momentum,
        selection_fields={"momentum": momentum},
        top_n=top_n,
        cost_bps=cost_bps,
    )
