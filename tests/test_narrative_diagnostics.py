from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from narrative_regime.narrative.diagnostics import audit_policy_features

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _features() -> pd.DataFrame:
    rows = 32
    level = np.arange(rows, dtype=float)
    return pd.DataFrame(
        {
            "record_id": [f"q{index}" for index in range(rows)],
            "period_end": pd.date_range("2018-03-31", periods=rows, freq="QE"),
            "level": level,
            "inverse": -level,
            "sparse": [0.0] * 31 + [1.0],
            "prior_section_similarity": [np.nan] + list(level[1:] / 100),
            "section_novelty": [np.nan] + list(1 - level[1:] / 100),
            "level_change_qoq": [np.nan] + [1.0] * 31,
        }
    )


def test_diagnostics_cover_missingness_persistence_and_collinearity() -> None:
    result = audit_policy_features(_features())

    assert result.summary["diagnostic_gate"] == "pass"
    assert result.summary["actual_missing_observations"] == 3
    assert result.summary["unexpected_missing_observations"] == 0
    assert result.summary["return_data_used"] is False
    assert result.summary["feature_selection_performed"] is False
    pairs = result.high_correlation_pairs
    assert (
        pairs["left_feature"].eq("level")
        & pairs["right_feature"].eq("inverse")
    ).any()


def test_unexpected_missing_value_blocks_gate() -> None:
    features = _features()
    features.loc[5, "level"] = np.nan

    result = audit_policy_features(features)

    assert result.summary["diagnostic_gate"] == "blocked"
    missingness = result.missingness.set_index("feature")
    assert missingness.loc["level", "unexpected_missing_observations"] == 1


def test_infinite_value_blocks_gate() -> None:
    features = _features()
    features.loc[5, "level"] = np.inf

    result = audit_policy_features(features)

    assert result.summary["diagnostic_gate"] == "blocked"
    assert result.summary["infinite_observations"] == 1


def test_market_relation_protocol_is_frozen_before_returns() -> None:
    protocol = json.loads(
        (PROJECT_ROOT / "configs/market_relation_protocol.json").read_text()
    )

    assert protocol["status"] == "frozen_before_market_relationships"
    assert protocol["timing_protocols"] == [
        "delay_24h",
        "delay_48h",
        "next_month",
    ]
    assert protocol["forward_windows_reference_sessions"] == [5, 20, 60]
    rules = protocol["reporting_rules"]
    assert rules["select_delay_from_results"] is False
    assert rules["select_feature_from_results"] is False
    assert rules["portfolio_construction_allowed"] is False
    roles = protocol["feature_roles"]
    assert "prior_section_similarity" in roles["primary_levels"]
    assert "section_novelty" in roles["audit_only_redundant"]
    assert all(
        feature.startswith("term_density_per_1000_")
        for feature in roles["primary_changes"]
    )
