from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from narrative_regime.baseline.attention import (
    FEATURE_WEIGHTS,
    PROXY_WEIGHT,
    engineer_attention_signals,
    run_attention_reproduction,
)
from narrative_regime.baseline.momentum import run_momentum_baseline


def _prices(periods: int = 130) -> pd.DataFrame:
    dates = pd.bdate_range("2021-10-01", periods=periods)
    rows = []
    for number, symbol in enumerate(["A", "B", "C", "D"]):
        for day, current_date in enumerate(dates):
            close = 100 * (1.0005 + number * 0.0002) ** day
            volume = 1_000 + number * 100 + day * (number + 1)
            rows.append(
                {
                    "date": current_date,
                    "symbol": symbol,
                    "close": close,
                    "volume": volume,
                    "amount": np.nan,
                    "is_tradable": True,
                }
            )
    return pd.DataFrame(rows)


def test_attention_uses_reported_amount_then_documented_fallback() -> None:
    prices = _prices()
    prices.loc[prices["symbol"].eq("A"), "amount"] = (
        prices.loc[prices["symbol"].eq("A"), "close"]
        * prices.loc[prices["symbol"].eq("A"), "volume"]
        * 1.01
    )

    signals = engineer_attention_signals(prices)

    assert signals.loc[signals["symbol"].eq("A"), "activity_value_source"].eq(
        "reported_amount"
    ).all()
    assert signals.loc[signals["symbol"].eq("B"), "activity_value_source"].eq(
        "close_x_volume"
    ).all()


def test_attention_labels_synthetic_no_trade_zero_separately() -> None:
    prices = _prices()
    prices["observation_status"] = "observed"
    marked_index = prices.index[0]
    prices.loc[marked_index, ["volume", "amount"]] = 0
    prices.loc[marked_index, "observation_status"] = "verified_no_trade"

    signals = engineer_attention_signals(prices)

    key = prices.loc[marked_index, ["date", "symbol"]]
    marked = signals.loc[
        signals["date"].eq(key["date"]) & signals["symbol"].eq(key["symbol"])
    ].iloc[0]
    assert marked["activity_value"] == 0
    assert marked["activity_value_source"] == "verified_no_trade_zero"


def test_attention_feature_formula_matches_predecessor_definition() -> None:
    prices = _prices()
    signals = engineer_attention_signals(prices)
    a_prices = prices.loc[prices["symbol"].eq("A")].reset_index(drop=True)
    row = signals.loc[signals["symbol"].eq("A")].reset_index(drop=True).iloc[80]
    activity = a_prices["close"] * a_prices["volume"]
    expected = np.log1p(activity.iloc[61:81].mean()) - np.log1p(
        activity.iloc[21:81].mean()
    )

    assert row["turnover_growth"] == pytest.approx(expected)


def test_future_changes_do_not_alter_past_attention_signals() -> None:
    prices = _prices()
    cutoff = pd.Timestamp("2022-02-28")
    original = engineer_attention_signals(prices)
    changed = prices.copy()
    changed.loc[changed["date"] > cutoff, ["close", "volume"]] *= 10
    revised = engineer_attention_signals(changed)
    columns = [*FEATURE_WEIGHTS, "attention_score", "composite_score"]

    pd.testing.assert_frame_equal(
        original.loc[original["date"] <= cutoff, columns].reset_index(drop=True),
        revised.loc[revised["date"] <= cutoff, columns].reset_index(drop=True),
    )


def test_composite_weight_is_fixed_at_fifty_percent() -> None:
    signals = engineer_attention_signals(_prices()).dropna(
        subset=["composite_score"]
    )
    expected = (
        (1 - PROXY_WEIGHT) * signals["z_momentum"]
        + PROXY_WEIGHT * signals["z_attention"]
    )

    pd.testing.assert_series_equal(
        signals["composite_score"], expected, check_names=False
    )
    assert PROXY_WEIGHT == 0.5


def test_reproduction_uses_same_momentum_benchmark_and_next_date_execution() -> None:
    prices = _prices()
    reproduction = run_attention_reproduction(prices, top_n=3, cost_bps=10)
    direct = run_momentum_baseline(prices, lookback=60, top_n=3, cost_bps=10)

    pd.testing.assert_frame_equal(reproduction.momentum.daily, direct.daily)
    first = reproduction.composite.selections.iloc[0]
    dates = pd.DatetimeIndex(sorted(prices["date"].unique()))
    location = dates.get_loc(first["signal_date"])
    assert first["execution_date"] == dates[location + 1]
    assert reproduction.activity_source_counts == {"close_x_volume": len(prices)}
    assert set(reproduction.comparison["period"]) >= {"Full sample", "2022-2023"}


def test_reproduction_rejects_negative_cost() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        run_attention_reproduction(_prices(), cost_bps=-1)
