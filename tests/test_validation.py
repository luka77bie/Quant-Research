from datetime import date

import pandas as pd
import pytest

from narrative_regime.data.validation import (
    market_frame_coverage_issues,
    normalize_market_frame,
)


def test_normalize_market_frame_sorts_and_deduplicates() -> None:
    frame = pd.DataFrame(
        {
            "date": ["2024-01-03", "2024-01-02", "2024-01-03"],
            "open": [10.0, 9.0, 10.5],
            "high": [11.0, 10.0, 11.5],
            "low": [9.5, 8.5, 10.0],
            "close": [10.5, 9.5, 11.0],
            "volume": [100, 90, 120],
        }
    )

    result = normalize_market_frame(frame)

    assert result["date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2024-01-02",
        "2024-01-03",
    ]
    assert result.loc[1, "close"] == 11.0
    assert "amount" in result


def test_normalize_market_frame_rejects_invalid_ohlc() -> None:
    frame = pd.DataFrame(
        {
            "date": ["2024-01-02"],
            "open": [10.0],
            "high": [9.0],
            "low": [8.0],
            "close": [10.5],
            "volume": [100],
        }
    )

    with pytest.raises(ValueError, match="relationships"):
        normalize_market_frame(frame)


def test_coverage_reports_late_start_and_early_end() -> None:
    frame = pd.DataFrame({"date": pd.to_datetime(["2024-01-15", "2024-01-16"])})

    issues = market_frame_coverage_issues(
        frame,
        expected_start=date(2024, 1, 1),
        expected_end=date(2024, 1, 31),
    )

    assert any("starts" in issue for issue in issues)
    assert any("ends" in issue for issue in issues)


def test_coverage_allows_weekend_and_holiday_boundaries() -> None:
    frame = pd.DataFrame(
        {"date": pd.to_datetime(["2024-01-02", "2024-01-15", "2024-01-29"])}
    )

    issues = market_frame_coverage_issues(
        frame,
        expected_start=date(2024, 1, 1),
        expected_end=date(2024, 1, 31),
    )

    assert issues == ()
