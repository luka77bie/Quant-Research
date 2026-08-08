from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class MarketRelationResult:
    audit: pd.DataFrame
    panel: pd.DataFrame
    asset_group_outcomes: pd.DataFrame
    dispersion_outcomes: pd.DataFrame
    symbol_relations: pd.DataFrame
    asset_group_relations: pd.DataFrame
    dispersion_relations: pd.DataFrame
    summary: dict[str, object]


def load_market_relation_protocol(path: Path) -> dict[str, object]:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("status") != "frozen_before_market_relationships":
        raise ValueError("market relation protocol is not frozen")
    return protocol


def build_descriptive_market_relations(
    features: pd.DataFrame,
    schedule: pd.DataFrame,
    prices: pd.DataFrame,
    universe: pd.DataFrame,
    protocol: dict[str, object],
    *,
    reference_symbol: str = "510300",
) -> MarketRelationResult:
    """Build pre-registered forward-return panels without portfolio selection."""
    _validate_inputs(features, schedule, prices, universe, protocol)
    windows = [int(value) for value in protocol["forward_windows_reference_sessions"]]
    protocols = [str(value) for value in protocol["timing_protocols"]]
    feature_columns = _numeric_feature_columns(features)
    feature_frame = features[["record_id", *feature_columns]].copy()

    market = prices.copy()
    market["date"] = pd.to_datetime(market["date"])
    market["symbol"] = market["symbol"].astype(str)
    if market.duplicated(["date", "symbol"]).any():
        raise ValueError("prices contain duplicate date-symbol rows")
    reference_dates = (
        market.loc[market["symbol"].eq(reference_symbol), "date"]
        .sort_values()
        .reset_index(drop=True)
    )
    if reference_dates.empty:
        raise ValueError(f"reference symbol not found: {reference_symbol}")
    date_locations = {date: index for index, date in enumerate(reference_dates)}
    market_indexed = market.set_index(["date", "symbol"]).sort_index()
    universe_records = universe.assign(symbol=universe["symbol"].astype(str)).to_dict(
        "records"
    )

    audit_rows = []
    selected_schedule = schedule.loc[schedule["protocol"].isin(protocols)].copy()
    selected_schedule["activation_date"] = pd.to_datetime(
        selected_schedule["activation_date"]
    )
    for activation in selected_schedule.to_dict("records"):
        activation_date = pd.Timestamp(activation["activation_date"])
        if activation_date not in date_locations:
            raise ValueError(
                f"activation date not in reference calendar: {activation_date}"
            )
        activation_location = date_locations[activation_date]
        for window in windows:
            end_location = activation_location + window
            end_date = (
                reference_dates.iloc[end_location]
                if end_location < len(reference_dates)
                else None
            )
            for asset in universe_records:
                result = _evaluate_symbol_window(
                    market_indexed,
                    reference_dates,
                    activation_date=activation_date,
                    activation_location=activation_location,
                    end_date=end_date,
                    symbol=str(asset["symbol"]),
                )
                audit_rows.append(
                    {
                        "protocol": activation["protocol"],
                        "record_id": activation["record_id"],
                        "period_end": activation["period_end"],
                        "activation_date": activation_date.date().isoformat(),
                        "window_sessions": window,
                        "end_date": (
                            end_date.date().isoformat() if end_date is not None else ""
                        ),
                        "symbol": str(asset["symbol"]),
                        "asset_group": asset["asset_group"],
                        "point_in_time_status": activation["point_in_time_status"],
                        **result,
                    }
                )

    audit = pd.DataFrame(audit_rows)
    panel = audit.loc[audit["status"].eq("ready")].merge(
        feature_frame, on="record_id", validate="many_to_one"
    )
    group_outcomes = _asset_group_outcomes(panel)
    dispersion_outcomes = _dispersion_outcomes(panel)
    symbol_relations = _relation_table(
        panel,
        feature_columns,
        group_columns=["protocol", "window_sessions", "symbol", "asset_group"],
        outcome_column="forward_return",
        outcome_type="per_symbol_forward_return",
    )
    group_relations = _relation_table(
        group_outcomes,
        feature_columns,
        group_columns=["protocol", "window_sessions", "asset_group"],
        outcome_column="equal_weight_forward_return",
        outcome_type="equal_weight_asset_group_forward_return",
    )
    dispersion_relations = _relation_table(
        dispersion_outcomes,
        feature_columns,
        group_columns=["protocol", "window_sessions"],
        outcome_column="cross_sectional_return_dispersion",
        outcome_type="cross_sectional_return_dispersion",
    )
    exclusions = audit.loc[audit["status"].ne("ready"), "exclusion_reason"]
    expected_combinations = len(selected_schedule) * len(windows) * len(universe)
    summary = {
        "feature_records": int(features["record_id"].nunique()),
        "timing_protocols": protocols,
        "forward_windows_reference_sessions": windows,
        "universe_symbols": len(universe),
        "expected_symbol_windows": expected_combinations,
        "ready_symbol_windows": len(panel),
        "excluded_symbol_windows": int(len(audit) - len(panel)),
        "exclusion_reasons": {
            key: int(value) for key, value in exclusions.value_counts().items()
        },
        "numeric_features_reported": len(feature_columns),
        "symbol_relation_rows": len(symbol_relations),
        "asset_group_relation_rows": len(group_relations),
        "dispersion_relation_rows": len(dispersion_relations),
        "lookahead_control_violations": int(
            panel["control_end_date"].ge(panel["activation_date"]).sum()
        ),
        "controls_attached_to_panel": True,
        "controls_used_in_relations": False,
        "relation_estimator": "unadjusted_pearson_and_spearman",
        "portfolio_constructed": False,
        "specification_selected": False,
        "inferential_tests_performed": False,
        "strict_point_in_time_claim": False,
        "research_use": "exploratory_only",
    }
    summary["market_relation_gate"] = (
        "pass"
        if len(audit) == expected_combinations
        and summary["lookahead_control_violations"] == 0
        else "blocked"
    )
    return MarketRelationResult(
        audit,
        panel,
        group_outcomes,
        dispersion_outcomes,
        symbol_relations,
        group_relations,
        dispersion_relations,
        summary,
    )


def _evaluate_symbol_window(
    market: pd.DataFrame,
    reference_dates: pd.Series,
    *,
    activation_date: pd.Timestamp,
    activation_location: int,
    end_date: pd.Timestamp | None,
    symbol: str,
) -> dict[str, object]:
    base = {
        "status": "excluded",
        "exclusion_reason": "",
        "start_close": math.nan,
        "end_close": math.nan,
        "forward_return": math.nan,
        "control_end_date": "",
        "lagged_mom60": math.nan,
        "lagged_volatility20": math.nan,
    }
    if end_date is None:
        return {**base, "exclusion_reason": "window_beyond_market_sample"}
    start_key = (activation_date, symbol)
    end_key = (end_date, symbol)
    if start_key not in market.index:
        return {**base, "exclusion_reason": "not_yet_in_dynamic_universe"}
    if end_key not in market.index:
        return {**base, "exclusion_reason": "missing_end_session"}
    start = market.loc[start_key]
    end = market.loc[end_key]
    if not bool(start["is_tradable"]):
        return {**base, "exclusion_reason": "activation_endpoint_not_tradable"}
    if not bool(end["is_tradable"]):
        return {**base, "exclusion_reason": "end_endpoint_not_tradable"}
    prior_location = activation_location - 1
    momentum_start_location = prior_location - 60
    if momentum_start_location < 0:
        return {**base, "exclusion_reason": "insufficient_control_history"}
    control_dates = reference_dates.iloc[momentum_start_location : prior_location + 1]
    control_keys = pd.MultiIndex.from_product([control_dates, [symbol]])
    available_keys = market.index.intersection(control_keys)
    if len(available_keys) != len(control_keys):
        return {**base, "exclusion_reason": "insufficient_control_history"}
    control = market.loc[control_keys].reset_index().sort_values("date")
    if not control["observation_status"].isin(
        ["observed", "verified_no_trade"]
    ).all():
        return {**base, "exclusion_reason": "unverified_control_observation"}
    control_returns = control["close"].pct_change()
    momentum = control["close"].iloc[-1] / control["close"].iloc[0] - 1
    volatility = control_returns.iloc[-20:].std(ddof=1) * math.sqrt(252)
    return {
        **base,
        "status": "ready",
        "start_close": float(start["close"]),
        "end_close": float(end["close"]),
        "forward_return": float(end["close"] / start["close"] - 1),
        "control_end_date": control["date"].iloc[-1].date().isoformat(),
        "lagged_mom60": float(momentum),
        "lagged_volatility20": float(volatility),
    }


def _asset_group_outcomes(panel: pd.DataFrame) -> pd.DataFrame:
    group_columns = [
        "protocol",
        "record_id",
        "period_end",
        "activation_date",
        "window_sessions",
        "asset_group",
    ]
    feature_columns = _numeric_feature_columns(panel)
    aggregations: dict[str, str] = {
        "forward_return": "mean",
        "lagged_mom60": "mean",
        "lagged_volatility20": "mean",
        "symbol": "nunique",
        **{column: "first" for column in feature_columns},
    }
    result = panel.groupby(group_columns, as_index=False).agg(aggregations)
    return result.rename(
        columns={
            "forward_return": "equal_weight_forward_return",
            "symbol": "eligible_symbols",
        }
    )


def _dispersion_outcomes(panel: pd.DataFrame) -> pd.DataFrame:
    group_columns = [
        "protocol",
        "record_id",
        "period_end",
        "activation_date",
        "window_sessions",
    ]
    feature_columns = _numeric_feature_columns(panel)
    aggregations = {
        "forward_return": "std",
        "symbol": "nunique",
        **{column: "first" for column in feature_columns},
    }
    result = panel.groupby(group_columns, as_index=False).agg(aggregations)
    return result.rename(
        columns={
            "forward_return": "cross_sectional_return_dispersion",
            "symbol": "eligible_symbols",
        }
    )


def _relation_table(
    outcomes: pd.DataFrame,
    feature_columns: list[str],
    *,
    group_columns: list[str],
    outcome_column: str,
    outcome_type: str,
) -> pd.DataFrame:
    rows = []
    for keys, group in outcomes.groupby(group_columns, dropna=False):
        key_values = keys if isinstance(keys, tuple) else (keys,)
        metadata = dict(zip(group_columns, key_values, strict=True))
        for feature in feature_columns:
            pair = group[[feature, outcome_column]].dropna()
            rows.append(
                {
                    "outcome_type": outcome_type,
                    **metadata,
                    "feature": feature,
                    "observations": len(pair),
                    "pearson": _safe_correlation(pair[feature], pair[outcome_column]),
                    "spearman": _safe_correlation(
                        pair[feature], pair[outcome_column], rank=True
                    ),
                }
            )
    return pd.DataFrame(rows)


def _safe_correlation(
    left: pd.Series, right: pd.Series, *, rank: bool = False
) -> float:
    if len(left) < 3 or left.nunique() < 2 or right.nunique() < 2:
        return math.nan
    if rank:
        left = left.rank()
        right = right.rank()
    return float(left.corr(right))


def _numeric_feature_columns(features: pd.DataFrame) -> list[str]:
    excluded = {
        "window_sessions",
        "start_close",
        "end_close",
        "forward_return",
        "lagged_mom60",
        "lagged_volatility20",
        "eligible_symbols",
        "cross_sectional_return_dispersion",
        "equal_weight_forward_return",
    }
    return [
        column
        for column in features.select_dtypes(include="number").columns
        if column not in excluded
    ]


def _validate_inputs(
    features: pd.DataFrame,
    schedule: pd.DataFrame,
    prices: pd.DataFrame,
    universe: pd.DataFrame,
    protocol: dict[str, object],
) -> None:
    requirements = {
        "features": ({"record_id"}, features),
        "schedule": (
            {
                "protocol",
                "record_id",
                "period_end",
                "activation_date",
                "point_in_time_status",
            },
            schedule,
        ),
        "prices": (
            {
                "date",
                "symbol",
                "close",
                "observation_status",
                "is_tradable",
            },
            prices,
        ),
        "universe": ({"symbol", "asset_group"}, universe),
    }
    for name, (required, frame) in requirements.items():
        missing = sorted(required - set(frame.columns))
        if missing:
            raise ValueError(f"{name} missing columns: {', '.join(missing)}")
    if protocol.get("status") != "frozen_before_market_relationships":
        raise ValueError("market relation protocol is not frozen")
    rules = protocol.get("reporting_rules", {})
    if rules.get("portfolio_construction_allowed") is not False:
        raise ValueError("protocol must prohibit portfolio construction")
    if features["record_id"].astype(str).duplicated().any():
        raise ValueError("features contain duplicate record IDs")
    if universe["symbol"].astype(str).duplicated().any():
        raise ValueError("universe contains duplicate symbols")
    protocols = [str(value) for value in protocol["timing_protocols"]]
    selected = schedule.loc[schedule["protocol"].isin(protocols)].copy()
    selected["record_id"] = selected["record_id"].astype(str)
    if selected.duplicated(["protocol", "record_id"]).any():
        raise ValueError("schedule contains duplicate protocol-record rows")
    expected_schedule = pd.MultiIndex.from_product(
        [protocols, features["record_id"].astype(str)],
        names=["protocol", "record_id"],
    )
    actual_schedule = pd.MultiIndex.from_frame(selected[["protocol", "record_id"]])
    missing_schedule = expected_schedule.difference(actual_schedule)
    unexpected_schedule = actual_schedule.difference(expected_schedule)
    if len(missing_schedule) or len(unexpected_schedule):
        raise ValueError(
            "schedule does not exactly cover every protocol-feature record"
        )
    windows = [int(value) for value in protocol["forward_windows_reference_sessions"]]
    if not windows or len(windows) != len(set(windows)) or min(windows) <= 0:
        raise ValueError("forward windows must be unique positive integers")
    feature_roles = protocol.get("feature_roles")
    if feature_roles:
        declared = [
            str(column)
            for columns in feature_roles.values()
            for column in columns
        ]
        if len(declared) != len(set(declared)):
            raise ValueError("feature roles contain duplicate columns")
        numeric = _numeric_feature_columns(features)
        if set(declared) != set(numeric):
            raise ValueError("feature roles do not match numeric feature columns")
