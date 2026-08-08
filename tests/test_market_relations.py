from __future__ import annotations

import math

import pandas as pd
import pytest

from narrative_regime.narrative.market_relations import (
    build_descriptive_market_relations,
)


def _inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dates = pd.bdate_range("2020-01-01", periods=130)
    feature_rows = []
    schedule_rows = []
    for index, activation_location in enumerate([70, 90]):
        record_id = f"q{index + 1}"
        feature_rows.append(
            {
                "record_id": record_id,
                "feature_level": float(index),
                "feature_change_qoq": math.nan if index == 0 else 1.0,
            }
        )
        schedule_rows.append(
            {
                "protocol": "delay_24h",
                "record_id": record_id,
                "period_end": dates[activation_location - 20].date().isoformat(),
                "activation_date": dates[activation_location].date().isoformat(),
                "point_in_time_status": "provisional",
            }
        )
    prices = []
    for symbol, scale, group in [("510300", 1.0, "equity"), ("511010", 2.0, "bond")]:
        for location, date in enumerate(dates):
            prices.append(
                {
                    "date": date,
                    "symbol": symbol,
                    "close": scale * (100 + location),
                    "observation_status": "observed",
                    "is_tradable": True,
                    "asset_group": group,
                }
            )
    universe = pd.DataFrame(
        [
            {"symbol": "510300", "asset_group": "equity"},
            {"symbol": "511010", "asset_group": "bond"},
        ]
    )
    return (
        pd.DataFrame(feature_rows),
        pd.DataFrame(schedule_rows),
        pd.DataFrame(prices),
        universe,
    )


def _protocol() -> dict[str, object]:
    return {
        "status": "frozen_before_market_relationships",
        "timing_protocols": ["delay_24h"],
        "forward_windows_reference_sessions": [5, 20],
        "reporting_rules": {"portfolio_construction_allowed": False},
    }


def test_market_panel_uses_activation_close_and_lagged_controls() -> None:
    features, schedule, prices, universe = _inputs()

    result = build_descriptive_market_relations(
        features, schedule, prices, universe, _protocol()
    )

    row = result.panel.loc[
        result.panel["record_id"].eq("q1")
        & result.panel["window_sessions"].eq(5)
        & result.panel["symbol"].eq("510300")
    ].iloc[0]
    assert row["forward_return"] == pytest.approx(175 / 170 - 1)
    assert row["lagged_mom60"] == pytest.approx(169 / 109 - 1)
    assert row["control_end_date"] < row["activation_date"]
    assert result.summary["lookahead_control_violations"] == 0
    assert result.summary["portfolio_constructed"] is False


def test_nontradable_endpoint_is_visible_exclusion() -> None:
    features, schedule, prices, universe = _inputs()
    activation = pd.Timestamp(schedule.loc[0, "activation_date"])
    mask = prices["date"].eq(activation) & prices["symbol"].eq("511010")
    prices.loc[mask, "is_tradable"] = False

    result = build_descriptive_market_relations(
        features, schedule, prices, universe, _protocol()
    )

    excluded = result.audit.loc[
        result.audit["record_id"].eq("q1")
        & result.audit["symbol"].eq("511010")
    ]
    assert excluded["status"].eq("excluded").all()
    assert excluded["exclusion_reason"].eq(
        "activation_endpoint_not_tradable"
    ).all()


def test_unfrozen_protocol_is_rejected() -> None:
    features, schedule, prices, universe = _inputs()
    protocol = _protocol()
    protocol["status"] = "draft"

    with pytest.raises(ValueError, match="not frozen"):
        build_descriptive_market_relations(
            features, schedule, prices, universe, protocol
        )


def test_incomplete_timing_schedule_is_rejected() -> None:
    features, schedule, prices, universe = _inputs()

    with pytest.raises(ValueError, match="exactly cover"):
        build_descriptive_market_relations(
            features,
            schedule.iloc[:-1],
            prices,
            universe,
            _protocol(),
        )
