from __future__ import annotations

import pandas as pd
import pytest

from narrative_regime.macro.panel import build_macro_panel


def _protocol() -> dict[str, object]:
    return {
        "protocol_version": 1,
        "sample": {
            "start_period": "2018-01",
            "end_period": "2018-12",
            "expected_missing_record_ids": [],
        },
        "dimensions": {
            "growth": {"source_family": "nbs_pmi"},
            "inflation": {"source_family": "nbs_cpi"},
            "liquidity": {"source_family": "pbc_m2"},
        },
        "minimum_state_observations": 2,
        "combined_states_permitted": False,
        "etf_returns_permitted": False,
    }


def _ledger() -> pd.DataFrame:
    periods = pd.period_range("2018-01", "2018-12", freq="M").astype(str)
    values = {
        "nbs_pmi": [49.0, 51.0] * 6,
        "nbs_cpi": [0.0, 1.0, 2.0, 3.0] * 3,
        "pbc_m2": [3.0, 2.0, 1.0, 0.0] * 3,
    }
    rows = []
    for family, family_values in values.items():
        for index, (period, value) in enumerate(
            zip(periods, family_values, strict=True)
        ):
            precision = "date" if family == "nbs_pmi" and index == 0 else "minute"
            release_at = (
                "2018-02-01"
                if precision == "date"
                else f"2018-{index + 1:02d}-28T01:00:00+00:00"
            )
            rows.append(
                {
                    "record_id": f"{family}_{period.replace('-', '_')}",
                    "source_family": family,
                    "period": period,
                    "release_at": release_at,
                    "release_timing_precision": precision,
                    "headline_value": value,
                    "article_status": "ready",
                }
            )
    return pd.DataFrame(rows)


def test_builds_return_blind_panel_with_conservative_date_timing() -> None:
    result = build_macro_panel(_ledger(), _protocol())

    assert result.summary["macro_panel_gate"] == "pass"
    assert result.summary["etf_returns_read"] is False
    assert result.panel["panel_ready"].all()
    assert result.panel.loc[0, "pmi_available_after"] == pd.Timestamp(
        "2018-02-01T16:00:00Z"
    )
    assert set(result.panel["growth_state"]) == {"contraction", "expansion"}
    assert result.panel["inflation_state"].isna().sum() == 3
    assert result.panel["liquidity_state"].isna().sum() == 3
    growth = result.state_counts[result.state_counts["dimension"].eq("growth")]
    assert growth["episodes"].eq(6).all()
    assert growth["maximum_episode_months"].eq(1).all()


def test_rejects_unregistered_missing_record() -> None:
    ledger = _ledger()
    ledger.loc[0, "article_status"] = "missing_source"

    with pytest.raises(ValueError, match="differ from frozen protocol"):
        build_macro_panel(ledger, _protocol())
