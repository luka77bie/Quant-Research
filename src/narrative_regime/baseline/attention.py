from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from narrative_regime.baseline.engine import (
    BacktestResult,
    close_panel,
    performance_metrics,
    run_monthly_ranked_backtest,
)
from narrative_regime.baseline.momentum import run_momentum_baseline

SHORT_WINDOW = 20
LONG_WINDOW = 60
PROXY_WEIGHT = 0.50
FEATURE_WEIGHTS = {
    "turnover_growth": 0.40,
    "volume_growth": 0.25,
    "attention_momentum": 0.25,
    "volatility_expansion": 0.10,
}
SUBPERIODS = {
    "Full sample": (None, None),
    "Pre-2022": (None, "2021-12-31"),
    "2022-2023": ("2022-01-01", "2023-12-31"),
    "2024+": ("2024-01-01", None),
}


@dataclass(frozen=True)
class AttentionReproductionResult:
    momentum: BacktestResult
    composite: BacktestResult
    signals: pd.DataFrame
    comparison: pd.DataFrame
    activity_source_counts: dict[str, int]


def engineer_attention_signals(prices: pd.DataFrame) -> pd.DataFrame:
    """Reproduce the predecessor proxy with a documented activity-value fallback."""
    required = {"date", "symbol", "close", "volume"}
    missing = sorted(required - set(prices.columns))
    if missing:
        raise ValueError(f"prices missing required columns: {', '.join(missing)}")

    columns = ["date", "symbol", "close", "volume"]
    if "amount" in prices:
        columns.append("amount")
    if "observation_status" in prices:
        columns.append("observation_status")
    frame = prices.loc[:, columns].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="raise").dt.normalize()
    frame["symbol"] = frame["symbol"].astype(str)
    for column in ["close", "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame.duplicated(["date", "symbol"]).any():
        raise ValueError("prices contain duplicate date-symbol rows")
    if frame[["close", "volume"]].isna().any().any():
        raise ValueError("close and volume must be non-missing")
    if (frame["close"] <= 0).any() or (frame["volume"] < 0).any():
        raise ValueError("close must be positive and volume must not be negative")

    if "amount" in frame:
        frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce")
        if (frame["amount"].dropna() < 0).any():
            raise ValueError("amount must not be negative")
        reported = frame["amount"].notna()
        frame["activity_value"] = frame["amount"].where(
            reported, frame["close"] * frame["volume"]
        )
        frame["activity_value_source"] = np.where(
            reported, "reported_amount", "close_x_volume"
        )
    else:
        frame["activity_value"] = frame["close"] * frame["volume"]
        frame["activity_value_source"] = "close_x_volume"

    if "observation_status" in frame:
        verified_no_trade = frame["observation_status"].eq("verified_no_trade")
        frame.loc[verified_no_trade, "activity_value_source"] = (
            "verified_no_trade_zero"
        )

    frame = frame.sort_values(["symbol", "date"]).reset_index(drop=True)
    groups: list[pd.DataFrame] = []
    for _, group in frame.groupby("symbol", sort=False):
        group = group.copy()
        daily_return = group["close"].pct_change(fill_method=None)
        activity_short = group["activity_value"].rolling(
            SHORT_WINDOW, min_periods=SHORT_WINDOW
        ).mean()
        activity_long = group["activity_value"].rolling(
            LONG_WINDOW, min_periods=LONG_WINDOW
        ).mean()
        volume_short = group["volume"].rolling(
            SHORT_WINDOW, min_periods=SHORT_WINDOW
        ).mean()
        volume_long = group["volume"].rolling(
            LONG_WINDOW, min_periods=LONG_WINDOW
        ).mean()
        activity_long_std = group["activity_value"].rolling(
            LONG_WINDOW, min_periods=LONG_WINDOW
        ).std(ddof=0)
        volatility_short = daily_return.rolling(
            SHORT_WINDOW, min_periods=SHORT_WINDOW
        ).std(ddof=0)
        volatility_long = daily_return.rolling(
            LONG_WINDOW, min_periods=LONG_WINDOW
        ).std(ddof=0)

        group["turnover_growth"] = np.log1p(activity_short) - np.log1p(
            activity_long
        )
        group["volume_growth"] = np.log1p(volume_short) - np.log1p(volume_long)
        group["attention_momentum"] = (
            group["activity_value"] - activity_long
        ) / activity_long_std.replace(0, np.nan)
        group["volatility_expansion"] = (
            volatility_short / volatility_long.replace(0, np.nan) - 1.0
        )
        groups.append(group)

    signals = pd.concat(groups, ignore_index=True)
    for feature in FEATURE_WEIGHTS:
        signals[f"z_{feature}"] = signals.groupby("date")[feature].transform(
            _cross_sectional_zscore
        )
    signals["attention_score"] = sum(
        weight * signals[f"z_{feature}"]
        for feature, weight in FEATURE_WEIGHTS.items()
    )

    close = close_panel(prices)
    momentum = close.div(close.shift(LONG_WINDOW)).sub(1.0)
    momentum_long = momentum.stack(future_stack=True).rename("momentum").reset_index()
    signals = signals.merge(
        momentum_long,
        on=["date", "symbol"],
        how="left",
        validate="one_to_one",
    )
    signals["z_momentum"] = signals.groupby("date")["momentum"].transform(
        _cross_sectional_zscore
    )
    signals["z_attention"] = signals.groupby("date")["attention_score"].transform(
        _cross_sectional_zscore
    )
    signals["composite_score"] = (
        (1.0 - PROXY_WEIGHT) * signals["z_momentum"]
        + PROXY_WEIGHT * signals["z_attention"]
    )
    required_signals = ["momentum", *FEATURE_WEIGHTS, "attention_score"]
    incomplete = signals[required_signals].isna().any(axis=1)
    signals.loc[incomplete, "composite_score"] = np.nan
    return signals.sort_values(["date", "symbol"]).reset_index(drop=True)


def run_attention_reproduction(
    prices: pd.DataFrame,
    *,
    top_n: int = 3,
    cost_bps: float = 10.0,
) -> AttentionReproductionResult:
    """Compare frozen MOM60 with the fixed 50% predecessor attention composite."""
    signals = engineer_attention_signals(prices)
    momentum_result = run_momentum_baseline(
        prices, lookback=LONG_WINDOW, top_n=top_n, cost_bps=cost_bps
    )
    panels = {
        column: signals.pivot(index="date", columns="symbol", values=column)
        for column in ["momentum", "attention_score", "composite_score"]
    }
    composite_result = run_monthly_ranked_backtest(
        prices,
        panels["composite_score"],
        selection_fields=panels,
        top_n=top_n,
        cost_bps=cost_bps,
    )
    comparison = _compare_subperiods(
        {
            "MOM60": momentum_result.daily,
            "MOM60 + 50% attention": composite_result.daily,
        }
    )
    source_counts = {
        str(key): int(value)
        for key, value in signals["activity_value_source"].value_counts().items()
    }
    return AttentionReproductionResult(
        momentum_result,
        composite_result,
        signals,
        comparison,
        source_counts,
    )


def _cross_sectional_zscore(values: pd.Series) -> pd.Series:
    standard_deviation = values.std(ddof=0)
    if pd.isna(standard_deviation) or np.isclose(standard_deviation, 0.0):
        return pd.Series(0.0, index=values.index)
    return (values - values.mean()) / standard_deviation


def _compare_subperiods(models: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for model, daily in models.items():
        for period, (start, end) in SUBPERIODS.items():
            selected = daily.copy()
            if start is not None:
                selected = selected.loc[selected.index >= pd.Timestamp(start)]
            if end is not None:
                selected = selected.loc[selected.index <= pd.Timestamp(end)]
            if selected.empty:
                continue
            selected = selected.copy()
            selected["equity"] = (1.0 + selected["net_return"]).cumprod()
            rows.append(
                {"model": model, "period": period, **performance_metrics(selected)}
            )
    return pd.DataFrame(rows)
