from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class BacktestResult:
    daily: pd.DataFrame
    selections: pd.DataFrame
    metrics: dict[str, float | int]


def run_monthly_ranked_backtest(
    prices: pd.DataFrame,
    scores: pd.DataFrame,
    *,
    selection_fields: Mapping[str, pd.DataFrame],
    top_n: int,
    cost_bps: float,
) -> BacktestResult:
    """Run the project's frozen monthly ranked-strategy execution policy."""
    if top_n < 1:
        raise ValueError("top_n must be at least 1")
    if cost_bps < 0:
        raise ValueError("cost_bps must not be negative")
    close = close_panel(prices)
    tradable = tradable_panel(prices, close)
    scores = scores.reindex(index=close.index, columns=close.columns)
    fields = {
        name: values.reindex(index=close.index, columns=close.columns)
        for name, values in selection_fields.items()
    }
    asset_returns = close.pct_change(fill_method=None)
    signal_dates = close.groupby(close.index.to_period("M")).tail(1).index

    target_changes: dict[pd.Timestamp, pd.Series] = {}
    selection_records: list[dict[str, object]] = []
    for signal_date in signal_dates:
        location = close.index.get_loc(signal_date)
        if location + 1 >= len(close.index):
            continue
        cross_section = scores.loc[signal_date].dropna().sort_values(ascending=False)
        if len(cross_section) < top_n:
            continue
        execution_date = close.index[location + 1]
        selected = cross_section.head(top_n)
        unavailable = ~tradable.loc[execution_date, selected.index]
        if unavailable.any():
            symbols = ", ".join(unavailable.index[unavailable])
            date_text = execution_date.date().isoformat()
            raise ValueError(
                f"selected assets are not tradable on {date_text}: {symbols}"
            )
        target = pd.Series(0.0, index=close.columns)
        target.loc[selected.index] = 1.0 / top_n
        target_changes[execution_date] = target
        for rank, symbol in enumerate(selected.index, start=1):
            record: dict[str, object] = {
                "signal_date": signal_date,
                "execution_date": execution_date,
                "rank": rank,
                "symbol": symbol,
            }
            for name, values in fields.items():
                record[name] = float(values.loc[signal_date, symbol])
            record["target_weight"] = 1.0 / top_n
            selection_records.append(record)

    if not target_changes:
        raise ValueError("no rebalance has enough eligible assets")

    first_execution = min(target_changes)
    simulation_dates = close.index[close.index >= first_execution]
    current_weights = pd.Series(0.0, index=close.columns)
    current_cash = 1.0
    equity = 1.0
    daily_records: list[dict[str, object]] = []
    for current_date in simulation_dates:
        turnover = 0.0
        if current_date in target_changes:
            target = target_changes[current_date]
            target_cash = 1.0 - float(target.sum())
            turnover = (
                float(target.sub(current_weights).abs().sum())
                + abs(target_cash - current_cash)
            ) / 2.0
            current_weights = target.copy()
            current_cash = target_cash

        returns_today = asset_returns.loc[current_date]
        missing_held = returns_today.isna() & current_weights.gt(0)
        if missing_held.any():
            symbols = ", ".join(missing_held.index[missing_held])
            date_text = current_date.date().isoformat()
            raise ValueError(
                f"missing return for held assets on {date_text}: {symbols}"
            )

        gross_return = float(returns_today.fillna(0.0).dot(current_weights))
        cost = turnover * (cost_bps / 10_000.0)
        net_return = gross_return - cost
        if net_return <= -1.0:
            raise ValueError("portfolio net value became non-positive")
        equity *= 1.0 + net_return
        daily_records.append(
            {
                "date": current_date,
                "gross_return": gross_return,
                "turnover": turnover,
                "cost": cost,
                "net_return": net_return,
                "equity": equity,
            }
        )

        gross_growth = 1.0 + gross_return
        if gross_growth <= 0:
            raise ValueError("portfolio gross value became non-positive")
        current_weights = current_weights.mul(1.0 + returns_today.fillna(0.0))
        current_weights = current_weights.div(gross_growth)
        current_cash /= gross_growth

    daily = pd.DataFrame(daily_records).set_index("date")
    daily.index.name = "date"
    selection_columns = [
        "signal_date",
        "execution_date",
        "rank",
        "symbol",
        *fields,
        "target_weight",
    ]
    selections = pd.DataFrame(selection_records, columns=selection_columns)
    return BacktestResult(daily, selections, performance_metrics(daily))


def close_panel(prices: pd.DataFrame) -> pd.DataFrame:
    required = {"date", "symbol", "close"}
    missing = sorted(required - set(prices.columns))
    if missing:
        raise ValueError(f"prices missing required columns: {', '.join(missing)}")

    frame = prices.loc[:, ["date", "symbol", "close"]].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="raise").dt.normalize()
    frame["symbol"] = frame["symbol"].astype(str)
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    if frame.duplicated(["date", "symbol"]).any():
        raise ValueError("prices contain duplicate date-symbol rows")
    if frame["close"].isna().any() or (frame["close"] <= 0).any():
        raise ValueError("close prices must be positive and non-missing")
    return frame.pivot(index="date", columns="symbol", values="close").sort_index()


def tradable_panel(prices: pd.DataFrame, close: pd.DataFrame) -> pd.DataFrame:
    if "is_tradable" not in prices:
        return pd.DataFrame(True, index=close.index, columns=close.columns)
    frame = prices.loc[:, ["date", "symbol", "is_tradable"]].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="raise").dt.normalize()
    frame["symbol"] = frame["symbol"].astype(str)
    if frame["is_tradable"].dtype != bool:
        normalized = frame["is_tradable"].astype(str).str.lower()
        if not normalized.isin({"true", "false"}).all():
            raise ValueError("is_tradable must contain only true or false")
        frame["is_tradable"] = normalized.eq("true")
    panel = frame.pivot(index="date", columns="symbol", values="is_tradable")
    panel = panel.reindex(index=close.index, columns=close.columns)
    return panel.eq(True)


def performance_metrics(daily: pd.DataFrame) -> dict[str, float | int]:
    returns = daily["net_return"]
    equity = daily["equity"]
    years = len(returns) / 252.0
    annual_return = float(equity.iloc[-1] ** (1.0 / years) - 1.0) if years else 0.0
    annual_volatility = float(returns.std(ddof=1) * (252.0**0.5))
    sharpe = (
        float(returns.mean() / returns.std(ddof=1) * (252.0**0.5))
        if annual_volatility > 0
        else 0.0
    )
    running_peak = equity.cummax().clip(lower=1.0)
    drawdown = equity.div(running_peak).sub(1.0)
    return {
        "observations": len(daily),
        "rebalances": int(daily["turnover"].gt(0).sum()),
        "total_return": float(equity.iloc[-1] - 1.0),
        "annual_return": annual_return,
        "annual_volatility": annual_volatility,
        "sharpe_zero_rate": sharpe,
        "max_drawdown": float(drawdown.min()),
        "total_turnover": float(daily["turnover"].sum()),
    }
