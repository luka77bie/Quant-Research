from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from narrative_regime.macro.payoff_atlas import (
    audit_payoff_atlas_protocol,
    load_payoff_atlas_protocol,
    validate_payoff_atlas_protocol,
)


def _protocol() -> dict[str, object]:
    return {
        "status": "frozen_before_etf_outcomes",
        "protocol_version": 1,
        "market_input": {
            "reference_symbol": "510300",
            "asset_groups": ["equity", "bond"],
        },
        "activation": {"delay_hours": 24},
        "forward_windows_reference_sessions": [5, 20],
        "primary_window_reference_sessions": 20,
        "state_comparisons": {
            "growth": ["contraction", "expansion"],
            "inflation": ["falling", "rising"],
            "liquidity": ["decelerating", "accelerating"],
        },
        "reporting": {
            "minimum_observations_per_state": 8,
            "minimum_episodes_per_state": 5,
            "fdr_reference": 0.1,
        },
        "restrictions": {
            "combined_states": False,
            "portfolio_construction": False,
            "specification_selection": False,
        },
    }


def test_protocol_audit_counts_one_multiplicity_family() -> None:
    universe = pd.DataFrame(
        [
            {
                "symbol": "510300",
                "asset_group": "equity",
                "available_from": "2012-05-28",
            },
            {
                "symbol": "511010",
                "asset_group": "bond",
                "available_from": "2013-03-25",
            },
        ]
    )

    summary = audit_payoff_atlas_protocol(_protocol(), universe)

    assert summary["planned_state_difference_tests"] == 12
    assert summary["etf_prices_read"] is False
    assert summary["payoff_protocol_gate"] == "pass"


def test_loader_rejects_draft_protocol(tmp_path: Path) -> None:
    protocol = _protocol()
    protocol["status"] = "draft"
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(protocol), encoding="utf-8")

    with pytest.raises(ValueError, match="not frozen"):
        load_payoff_atlas_protocol(path)


def test_protocol_rejects_enabled_portfolio() -> None:
    protocol = _protocol()
    protocol["restrictions"]["portfolio_construction"] = True

    with pytest.raises(ValueError, match="must be disabled"):
        validate_payoff_atlas_protocol(protocol)
