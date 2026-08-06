from __future__ import annotations

import pandas as pd
import pytest

from narrative_regime.baseline.momentum import run_momentum_baseline


def _prices() -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-29", "2024-02-07")
    values = {
        "A": [100, 110, 120, 132, 133, 134, 135, 136],
        "B": [100, 105, 108, 108, 109, 110, 111, 112],
        "C": [100, 101, 102, 500, 501, 502, 503, 504],
    }
    return pd.DataFrame(
        [
            {"date": current_date, "symbol": symbol, "close": close}
            for symbol, closes in values.items()
            for current_date, close in zip(dates, closes, strict=True)
        ]
    )


def test_momentum_uses_month_end_signal_and_next_date_execution() -> None:
    result = run_momentum_baseline(_prices(), lookback=2, top_n=2, cost_bps=10)

    first = result.selections[result.selections["signal_date"] == "2024-01-31"]
    assert first["symbol"].tolist() == ["A", "B"]
    assert first["execution_date"].dt.strftime("%Y-%m-%d").unique().tolist() == [
        "2024-02-01"
    ]
    assert result.daily.index[0] == pd.Timestamp("2024-02-01")
    assert result.daily.iloc[0]["turnover"] == pytest.approx(1.0)
    assert result.daily.iloc[0]["gross_return"] == pytest.approx(0.05)
    assert result.daily.iloc[0]["net_return"] == pytest.approx(0.049)


def test_momentum_does_not_rebalance_equal_weights_every_day() -> None:
    result = run_momentum_baseline(_prices(), lookback=2, top_n=2, cost_bps=0)

    assert result.daily.iloc[1]["turnover"] == 0
    expected_a_weight = (0.5 * (133 / 120)) / (
        0.5 * (133 / 120) + 0.5 * (109 / 108)
    )
    next_a_return = 134 / 133 - 1
    next_b_return = 110 / 109 - 1
    expected = (
        expected_a_weight * next_a_return
        + (1 - expected_a_weight) * next_b_return
    )
    assert result.daily.iloc[2]["gross_return"] == pytest.approx(expected)


def test_momentum_rejects_missing_return_for_selected_asset() -> None:
    prices = _prices()
    prices = prices[
        ~((prices["date"] == pd.Timestamp("2024-02-01")) & (prices["symbol"] == "A"))
    ]

    with pytest.raises(ValueError, match="missing return for held assets"):
        run_momentum_baseline(prices, lookback=2, top_n=2)


def test_momentum_rejects_duplicate_rows() -> None:
    prices = pd.concat([_prices(), _prices().iloc[[0]]], ignore_index=True)

    with pytest.raises(ValueError, match="duplicate"):
        run_momentum_baseline(prices, lookback=2, top_n=2)


def test_drawdown_includes_loss_on_first_invested_day() -> None:
    prices = _prices()
    prices.loc[
        (prices["date"] == pd.Timestamp("2024-02-01")) & prices["symbol"].eq("A"),
        "close",
    ] = 60
    prices.loc[
        (prices["date"] == pd.Timestamp("2024-02-01")) & prices["symbol"].eq("B"),
        "close",
    ] = 54

    result = run_momentum_baseline(prices, lookback=2, top_n=2, cost_bps=0)

    assert result.metrics["max_drawdown"] == pytest.approx(-0.5)
