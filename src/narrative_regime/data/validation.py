from __future__ import annotations

from datetime import date

import pandas as pd

CANONICAL_COLUMNS = ["date", "open", "high", "low", "close", "volume", "amount"]
REQUIRED_COLUMNS = ["date", "open", "high", "low", "close", "volume"]
DEFAULT_BOUNDARY_TOLERANCE_DAYS = 7
DEFAULT_MAX_INTERNAL_GAP_DAYS = 14


def normalize_market_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize one symbol's daily market data."""
    missing = sorted(set(REQUIRED_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"missing required columns: {', '.join(missing)}")

    result = frame.copy()
    if "amount" not in result:
        result["amount"] = pd.NA

    result = result[CANONICAL_COLUMNS]
    result["date"] = pd.to_datetime(result["date"], errors="raise").dt.normalize()

    numeric_columns = ["open", "high", "low", "close", "volume", "amount"]
    for column in numeric_columns:
        result[column] = pd.to_numeric(result[column], errors="coerce")

    if result[["open", "high", "low", "close"]].isna().any().any():
        raise ValueError("OHLC columns contain non-numeric or missing values")
    if (result[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("OHLC prices must be positive")
    if (result["volume"].dropna() < 0).any():
        raise ValueError("volume must not be negative")

    result = result.sort_values("date").drop_duplicates("date", keep="last")
    if result.empty:
        raise ValueError("provider returned no usable rows")

    invalid_bar = (result["high"] < result[["open", "close", "low"]].max(axis=1)) | (
        result["low"] > result[["open", "close", "high"]].min(axis=1)
    )
    if invalid_bar.any():
        raise ValueError("OHLC price relationships are inconsistent")

    return result.reset_index(drop=True)


def market_frame_coverage_issues(
    frame: pd.DataFrame,
    *,
    expected_start: date,
    expected_end: date,
    boundary_tolerance_days: int = DEFAULT_BOUNDARY_TOLERANCE_DAYS,
    max_internal_gap_days: int = DEFAULT_MAX_INTERNAL_GAP_DAYS,
) -> tuple[str, ...]:
    """Return visible coverage problems without guessing missing trading days."""
    if boundary_tolerance_days < 0 or max_internal_gap_days < 1:
        raise ValueError("coverage tolerances must be non-negative")

    dates = pd.to_datetime(frame["date"], errors="raise").sort_values()
    observed_start = dates.iloc[0].date()
    observed_end = dates.iloc[-1].date()
    issues: list[str] = []

    start_gap = (observed_start - expected_start).days
    if start_gap > boundary_tolerance_days:
        issues.append(
            f"history starts {start_gap} calendar days late "
            f"({observed_start.isoformat()})"
        )

    end_gap = (expected_end - observed_end).days
    if end_gap > boundary_tolerance_days:
        issues.append(
            f"history ends {end_gap} calendar days early "
            f"({observed_end.isoformat()})"
        )

    calendar_gaps = dates.diff().dt.days.dropna()
    if not calendar_gaps.empty and int(calendar_gaps.max()) > max_internal_gap_days:
        issues.append(
            f"maximum internal calendar gap is {int(calendar_gaps.max())} days"
        )

    return tuple(issues)
