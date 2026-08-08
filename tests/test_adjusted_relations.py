from __future__ import annotations

import pandas as pd

from narrative_regime.narrative.adjusted_relations import (
    build_adjusted_market_relations,
)


def _protocol() -> dict[str, object]:
    return {
        "status": "frozen_before_adjusted_market_relationships",
        "evidence_status": "post_descriptive_exploratory",
        "timing_protocols": ["delay_24h"],
        "forward_windows_reference_sessions": [5],
        "primary_features": ["feature_level", "feature_change_qoq"],
        "measurement_control_mapping": {
            "level": "section_character_count",
            "change": "section_character_change_qoq",
            "change_feature_suffix": "_change_qoq",
        },
        "market_controls": ["lagged_mom60", "lagged_volatility20"],
        "models": {
            "primary_pooled_asset_group": {"minimum_event_clusters": 24},
            "secondary_asset_group": {"minimum_events": 24},
            "secondary_dispersion": {
                "minimum_events": 24,
                "hac_lags_by_window": {"5": 0},
            },
        },
        "numerical_gates": {
            "minimum_predictor_standard_deviation": 1e-12,
            "maximum_absolute_feature_control_correlation": 0.95,
            "maximum_design_condition_number": 1000.0,
        },
        "multiplicity": {"reference_fdr": 0.1},
        "reporting_rules": {"portfolio_construction_allowed": False},
    }


def _panel() -> pd.DataFrame:
    rows = []
    for event in range(30):
        feature = (event % 7) - 3 + event * 0.03
        feature_change = ((event * 3) % 11) - 5 + event * 0.01
        momentum = ((event * 5) % 13) / 10
        volatility = 0.1 + ((event * 7) % 9) / 100
        for group_index, group in enumerate(["equity", "bond"]):
            for symbol_index in range(2):
                outcome = (
                    0.6 * feature
                    + 0.2 * momentum
                    - 0.1 * volatility
                    + group_index * 0.4
                    + symbol_index * (0.05 + 0.01 * event)
                )
                rows.append(
                    {
                        "protocol": "delay_24h",
                        "record_id": f"event-{event:02d}",
                        "period_end": f"2020-{event + 1:02d}-01",
                        "activation_date": f"2020-{event + 1:02d}-02",
                        "window_sessions": 5,
                        "symbol": f"{group}-{symbol_index}",
                        "asset_group": group,
                        "point_in_time_status": "provisional",
                        "forward_return": outcome,
                        "lagged_mom60": momentum + symbol_index * 0.02,
                        "lagged_volatility20": volatility + symbol_index * 0.001,
                        "feature_level": feature,
                        "feature_change_qoq": feature_change,
                        "section_character_count": 2000 + event * 13,
                        "section_character_change_qoq": (event % 5) * 17 - 30,
                    }
                )
    return pd.DataFrame(rows)


def test_adjusted_grid_reports_every_frozen_model() -> None:
    result = build_adjusted_market_relations(_panel(), _protocol())

    assert len(result.pooled_relations) == 2
    assert len(result.asset_group_relations) == 4
    assert len(result.dispersion_relations) == 2
    assert result.pooled_relations["status"].eq("ready").all()
    assert result.pooled_relations.loc[
        result.pooled_relations["feature"].eq("feature_level"),
        "standardized_beta",
    ].iloc[0] > 0
    assert result.pooled_relations["inference_degrees_freedom"].eq(29).all()
    assert result.asset_group_relations["p_value"].isna().all()
    assert result.summary["portfolio_constructed"] is False
    assert result.summary["adjusted_relation_gate"] == "pass"


def test_feature_control_collinearity_is_visible_exclusion() -> None:
    panel = _panel()
    panel["feature_level"] = panel["section_character_count"]

    result = build_adjusted_market_relations(panel, _protocol())

    row = result.pooled_relations.loc[
        result.pooled_relations["feature"].eq("feature_level")
    ].iloc[0]
    assert row["status"] == "excluded"
    assert row["exclusion_reason"] == "feature_control_collinearity"
