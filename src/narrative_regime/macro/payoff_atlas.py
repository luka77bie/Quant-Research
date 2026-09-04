from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

EXPECTED_DIMENSIONS = {"growth", "inflation", "liquidity"}


def load_payoff_atlas_protocol(path: Path) -> dict[str, object]:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    validate_payoff_atlas_protocol(protocol)
    return protocol


def validate_payoff_atlas_protocol(protocol: dict[str, object]) -> None:
    if protocol.get("status") != "frozen_before_etf_outcomes":
        raise ValueError("payoff atlas protocol is not frozen")
    if protocol.get("protocol_version") != 1:
        raise ValueError("unsupported payoff atlas protocol version")

    windows = protocol.get("forward_windows_reference_sessions")
    if not isinstance(windows, list) or not windows:
        raise ValueError("forward windows must be a non-empty list")
    normalized_windows = [int(value) for value in windows]
    if any(value < 1 for value in normalized_windows):
        raise ValueError("forward windows must be positive")
    if len(normalized_windows) != len(set(normalized_windows)):
        raise ValueError("forward windows must be unique")
    if int(protocol.get("primary_window_reference_sessions", 0)) not in windows:
        raise ValueError("primary window must be included in forward windows")

    comparisons = protocol.get("state_comparisons")
    if not isinstance(comparisons, dict) or set(comparisons) != EXPECTED_DIMENSIONS:
        raise ValueError("state comparisons must cover exactly three dimensions")
    if any(
        not isinstance(states, list)
        or len(states) != 2
        or len(set(states)) != 2
        for states in comparisons.values()
    ):
        raise ValueError("each dimension must register two distinct states")

    activation = protocol.get("activation", {})
    if int(activation.get("delay_hours", -1)) < 0:
        raise ValueError("activation delay must not be negative")
    reporting = protocol.get("reporting", {})
    if int(reporting.get("minimum_observations_per_state", 0)) < 1:
        raise ValueError("minimum observations must be positive")
    if int(reporting.get("minimum_episodes_per_state", 0)) < 1:
        raise ValueError("minimum episodes must be positive")
    fdr = float(reporting.get("fdr_reference", math.nan))
    if not 0 < fdr < 1:
        raise ValueError("FDR reference must lie between zero and one")

    restrictions = protocol.get("restrictions", {})
    prohibited = (
        "combined_states",
        "portfolio_construction",
        "specification_selection",
    )
    if any(restrictions.get(key) is not False for key in prohibited):
        raise ValueError("combined states, portfolios, and selection must be disabled")


def audit_payoff_atlas_protocol(
    protocol: dict[str, object], universe: pd.DataFrame
) -> dict[str, object]:
    validate_payoff_atlas_protocol(protocol)
    required = {"symbol", "asset_group", "available_from"}
    missing = sorted(required - set(universe.columns))
    if missing:
        raise ValueError(f"ETF universe missing columns: {', '.join(missing)}")
    if universe["symbol"].astype(str).duplicated().any():
        raise ValueError("ETF universe contains duplicate symbols")
    pd.to_datetime(universe["available_from"], errors="raise")

    expected_groups = set(protocol["market_input"]["asset_groups"])
    observed_groups = set(universe["asset_group"].astype(str))
    if observed_groups != expected_groups:
        raise ValueError("ETF universe groups differ from frozen protocol")
    reference_symbol = str(protocol["market_input"]["reference_symbol"])
    if reference_symbol not in set(universe["symbol"].astype(str)):
        raise ValueError("reference symbol is missing from ETF universe")

    windows = protocol["forward_windows_reference_sessions"]
    tests = len(EXPECTED_DIMENSIONS) * len(expected_groups) * len(windows)
    return {
        "protocol_status": protocol["status"],
        "universe_symbols": len(universe),
        "asset_groups": sorted(expected_groups),
        "dimensions": sorted(EXPECTED_DIMENSIONS),
        "forward_windows_reference_sessions": windows,
        "planned_state_difference_tests": tests,
        "multiplicity_family_tests": tests,
        "etf_prices_read": False,
        "portfolio_constructed": False,
        "payoff_protocol_gate": "pass",
    }
