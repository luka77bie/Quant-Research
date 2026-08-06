from __future__ import annotations

import pandas as pd
import pytest

from narrative_regime.narrative.timing import build_timing_joins


def _features() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "record_id": "q1",
                "period_end": "2020-03-31",
                "published_at": "2020-05-01T02:00:00Z",
                "available_at": "2020-05-02T02:00:00Z",
                "point_in_time_status": "provisional",
                "feature": 1.0,
            },
            {
                "record_id": "q2",
                "period_end": "2020-06-30",
                "published_at": "2020-06-03T00:00:00Z",
                "available_at": "2020-06-04T00:00:00Z",
                "point_in_time_status": "provisional",
                "feature": 2.0,
            },
        ]
    )


def _calendar() -> pd.DataFrame:
    dates = pd.to_datetime(
        [
            "2020-05-01",
            "2020-05-04",
            "2020-05-05",
            "2020-05-06",
            "2020-06-01",
            "2020-06-02",
            "2020-06-04",
            "2020-06-05",
            "2020-06-08",
            "2020-07-01",
        ]
    )
    return pd.DataFrame(
        {
            "date": list(dates) * 2,
            "symbol": ["510300"] * len(dates) + ["other"] * len(dates),
        }
    )


def test_timing_protocols_map_to_first_eligible_open() -> None:
    result = build_timing_joins(_features(), _calendar())
    schedule = result.schedule.set_index(["protocol", "record_id"])

    assert schedule.loc[("delay_24h", "q1"), "activation_date"] == "2020-05-04"
    assert schedule.loc[("delay_48h", "q1"), "activation_date"] == "2020-05-04"
    assert schedule.loc[("delay_24h", "q2"), "activation_date"] == "2020-06-04"
    assert schedule.loc[("delay_48h", "q2"), "activation_date"] == "2020-06-05"
    assert schedule.loc[("next_month", "q1"), "activation_date"] == "2020-06-01"
    assert schedule.loc[("next_month", "q2"), "activation_date"] == "2020-07-01"
    assert result.summary["lookahead_violations"] == 0
    assert result.summary["price_values_used"] is False


def test_asof_calendar_never_exposes_future_feature() -> None:
    result = build_timing_joins(_features(), _calendar())
    calendar = result.calendar
    delayed = calendar.loc[calendar["protocol"].eq("delay_48h")].set_index("date")

    assert pd.isna(delayed.loc[pd.Timestamp("2020-05-01"), "record_id"])
    assert delayed.loc[pd.Timestamp("2020-05-04"), "record_id"] == "q1"
    assert delayed.loc[pd.Timestamp("2020-06-05"), "record_id"] == "q2"
    exposed = calendar.loc[calendar["feature_available"]]
    assert exposed["session_open_at"].ge(exposed["activation_open_at"]).all()
    assert exposed["activation_open_at"].ge(exposed["effective_at"]).all()


def test_duplicate_reference_dates_are_blocked() -> None:
    calendar = _calendar()
    duplicate = calendar.loc[
        calendar["symbol"].eq("510300") & calendar["date"].eq("2020-05-01")
    ]
    calendar = pd.concat([calendar, duplicate], ignore_index=True)

    with pytest.raises(ValueError, match="duplicate dates"):
        build_timing_joins(_features(), calendar)


def test_missing_future_session_is_blocked() -> None:
    features = _features().iloc[[0]].copy()
    features["available_at"] = "2020-07-01T00:00:00Z"

    with pytest.raises(ValueError, match="no reference session"):
        build_timing_joins(features, _calendar())
