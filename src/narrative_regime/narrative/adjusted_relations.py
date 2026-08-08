from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


@dataclass(frozen=True)
class AdjustedRelationResult:
    asset_group_panel: pd.DataFrame
    dispersion_panel: pd.DataFrame
    pooled_relations: pd.DataFrame
    asset_group_relations: pd.DataFrame
    dispersion_relations: pd.DataFrame
    summary: dict[str, object]


def load_adjusted_relation_protocol(path: Path) -> dict[str, object]:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("status") != "frozen_before_adjusted_market_relationships":
        raise ValueError("adjusted relation protocol is not frozen")
    return protocol


def build_adjusted_market_relations(
    panel: pd.DataFrame,
    protocol: dict[str, object],
) -> AdjustedRelationResult:
    """Run the frozen post-descriptive adjusted relationship grid."""
    _validate_inputs(panel, protocol)
    features = [str(value) for value in protocol["primary_features"]]
    protocols = [str(value) for value in protocol["timing_protocols"]]
    windows = [int(value) for value in protocol["forward_windows_reference_sessions"]]
    asset_group_panel = _build_asset_group_panel(panel, features, protocol)
    dispersion_panel = _build_dispersion_panel(panel, features, protocol)

    pooled_rows: list[dict[str, object]] = []
    group_rows: list[dict[str, object]] = []
    dispersion_rows: list[dict[str, object]] = []
    for timing in protocols:
        for window in windows:
            group_sample = asset_group_panel.loc[
                asset_group_panel["protocol"].eq(timing)
                & asset_group_panel["window_sessions"].eq(window)
            ]
            dispersion_sample = dispersion_panel.loc[
                dispersion_panel["protocol"].eq(timing)
                & dispersion_panel["window_sessions"].eq(window)
            ]
            for feature in features:
                measurement_control = _measurement_control(feature, protocol)
                pooled_rows.append(
                    _fit_specification(
                        group_sample,
                        feature=feature,
                        measurement_control=measurement_control,
                        outcome="equal_weight_forward_return",
                        covariance="record_id_cluster_robust_cr1",
                        minimum_events=int(
                            protocol["models"]["primary_pooled_asset_group"][
                                "minimum_event_clusters"
                            ]
                        ),
                        protocol=protocol,
                        fixed_effect="asset_group",
                        cluster_column="record_id",
                        metadata={
                            "model_family": "primary_pooled_asset_group",
                            "protocol": timing,
                            "window_sessions": window,
                            "feature": feature,
                        },
                    )
                )
                for asset_group, sample in group_sample.groupby("asset_group"):
                    group_rows.append(
                        _fit_specification(
                            sample,
                            feature=feature,
                            measurement_control=measurement_control,
                            outcome="equal_weight_forward_return",
                            covariance="none_descriptive_coefficient_only",
                            minimum_events=int(
                                protocol["models"]["secondary_asset_group"][
                                    "minimum_events"
                                ]
                            ),
                            protocol=protocol,
                            metadata={
                                "model_family": "secondary_asset_group",
                                "protocol": timing,
                                "window_sessions": window,
                                "asset_group": asset_group,
                                "feature": feature,
                            },
                        )
                    )
                hac_lags = int(
                    protocol["models"]["secondary_dispersion"][
                        "hac_lags_by_window"
                    ][str(window)]
                )
                dispersion_rows.append(
                    _fit_specification(
                        dispersion_sample,
                        feature=feature,
                        measurement_control=measurement_control,
                        outcome="cross_sectional_return_dispersion",
                        covariance="newey_west_bartlett",
                        minimum_events=int(
                            protocol["models"]["secondary_dispersion"][
                                "minimum_events"
                            ]
                        ),
                        protocol=protocol,
                        hac_lags=hac_lags,
                        metadata={
                            "model_family": "secondary_dispersion",
                            "protocol": timing,
                            "window_sessions": window,
                            "feature": feature,
                        },
                    )
                )

    pooled = _apply_bh(pd.DataFrame(pooled_rows))
    group_relations = pd.DataFrame(group_rows)
    dispersion = _apply_bh(pd.DataFrame(dispersion_rows))
    pooled = _mark_candidates(pooled, protocol)
    expected_pooled = len(protocols) * len(windows) * len(features)
    expected_groups = expected_pooled * panel["asset_group"].nunique()
    summary = {
        "evidence_status": protocol["evidence_status"],
        "descriptive_results_already_observed": True,
        "primary_features": len(features),
        "timing_protocols": protocols,
        "forward_windows_reference_sessions": windows,
        "asset_groups": int(panel["asset_group"].nunique()),
        "expected_pooled_models": expected_pooled,
        "ready_pooled_models": int(pooled["status"].eq("ready").sum()),
        "excluded_pooled_models": int(pooled["status"].ne("ready").sum()),
        "expected_asset_group_models": expected_groups,
        "ready_asset_group_models": int(
            group_relations["status"].eq("ready").sum()
        ),
        "excluded_asset_group_models": int(
            group_relations["status"].ne("ready").sum()
        ),
        "expected_dispersion_models": expected_pooled,
        "ready_dispersion_models": int(dispersion["status"].eq("ready").sum()),
        "excluded_dispersion_models": int(
            dispersion["status"].ne("ready").sum()
        ),
        "pooled_models_q_at_or_below_0_10": int(
            pooled["bh_q_value"].le(0.10).fillna(False).sum()
        ),
        "candidate_pooled_models": int(pooled["candidate_relation"].sum()),
        "dispersion_models_q_at_or_below_0_10": int(
            dispersion["bh_q_value"].le(0.10).fillna(False).sum()
        ),
        "portfolio_constructed": False,
        "confirmatory_claim_allowed": False,
        "strict_point_in_time_claim": False,
        "independent_validation_required": True,
    }
    summary["adjusted_relation_gate"] = (
        "pass"
        if len(pooled) == expected_pooled
        and len(group_relations) == expected_groups
        and len(dispersion) == expected_pooled
        else "blocked"
    )
    return AdjustedRelationResult(
        asset_group_panel,
        dispersion_panel,
        pooled,
        group_relations,
        dispersion,
        summary,
    )


def _build_asset_group_panel(
    panel: pd.DataFrame,
    features: list[str],
    protocol: dict[str, object],
) -> pd.DataFrame:
    measurement_controls = _measurement_controls(protocol)
    keys = [
        "protocol",
        "record_id",
        "period_end",
        "activation_date",
        "window_sessions",
        "asset_group",
        "point_in_time_status",
    ]
    aggregations = {
        "forward_return": "mean",
        "lagged_mom60": "mean",
        "lagged_volatility20": "mean",
        "symbol": "nunique",
        **{column: "first" for column in [*features, *measurement_controls]},
    }
    result = panel.groupby(keys, as_index=False).agg(aggregations)
    return result.rename(
        columns={
            "forward_return": "equal_weight_forward_return",
            "symbol": "eligible_symbols",
        }
    )


def _build_dispersion_panel(
    panel: pd.DataFrame,
    features: list[str],
    protocol: dict[str, object],
) -> pd.DataFrame:
    measurement_controls = _measurement_controls(protocol)
    keys = [
        "protocol",
        "record_id",
        "period_end",
        "activation_date",
        "window_sessions",
        "point_in_time_status",
    ]
    aggregations = {
        "forward_return": "std",
        "lagged_mom60": "mean",
        "lagged_volatility20": "mean",
        "symbol": "nunique",
        **{column: "first" for column in [*features, *measurement_controls]},
    }
    result = panel.groupby(keys, as_index=False).agg(aggregations)
    return result.rename(
        columns={
            "forward_return": "cross_sectional_return_dispersion",
            "symbol": "eligible_symbols",
        }
    )


def _fit_specification(
    frame: pd.DataFrame,
    *,
    feature: str,
    measurement_control: str,
    outcome: str,
    covariance: str,
    minimum_events: int,
    protocol: dict[str, object],
    metadata: dict[str, object],
    fixed_effect: str | None = None,
    cluster_column: str | None = None,
    hac_lags: int = 0,
) -> dict[str, object]:
    controls = [str(value) for value in protocol["market_controls"]]
    columns = [
        outcome,
        feature,
        measurement_control,
        *controls,
        "record_id",
        "period_end",
    ]
    if fixed_effect:
        columns.append(fixed_effect)
    sample = frame[columns].dropna().sort_values(["period_end", "record_id"]).copy()
    base = {
        **metadata,
        "measurement_control": measurement_control,
        "covariance": covariance,
        "status": "excluded",
        "exclusion_reason": "",
        "observations": len(sample),
        "event_clusters": int(sample["record_id"].nunique()),
        "standardized_beta": math.nan,
        "standard_error": math.nan,
        "test_statistic": math.nan,
        "inference_degrees_freedom": math.nan,
        "p_value": math.nan,
        "bh_q_value": math.nan,
        "ci_95_low": math.nan,
        "ci_95_high": math.nan,
        "r_squared": math.nan,
        "condition_number": math.nan,
        "maximum_absolute_feature_control_correlation": math.nan,
    }
    if base["event_clusters"] < minimum_events:
        return {**base, "exclusion_reason": "insufficient_events"}
    continuous = [feature, measurement_control, *controls]
    minimum_sd = float(
        protocol["numerical_gates"]["minimum_predictor_standard_deviation"]
    )
    standard_deviations = sample[[outcome, *continuous]].std(ddof=1)
    if standard_deviations.le(minimum_sd).any():
        return {**base, "exclusion_reason": "near_zero_standard_deviation"}
    feature_control_correlation = sample[continuous].corr()[feature].drop(feature)
    maximum_correlation = float(feature_control_correlation.abs().max())
    base["maximum_absolute_feature_control_correlation"] = maximum_correlation
    correlation_limit = float(
        protocol["numerical_gates"][
            "maximum_absolute_feature_control_correlation"
        ]
    )
    if maximum_correlation > correlation_limit:
        return {**base, "exclusion_reason": "feature_control_collinearity"}
    standardized = (
        sample[[outcome, *continuous]]
        - sample[[outcome, *continuous]].mean()
    ) / standard_deviations
    design_parts = [
        np.ones((len(sample), 1)),
        standardized[continuous].to_numpy(dtype=float),
    ]
    if fixed_effect:
        dummies = pd.get_dummies(sample[fixed_effect], drop_first=True, dtype=float)
        design_parts.append(dummies.to_numpy(dtype=float))
    design = np.column_stack(design_parts)
    response = standardized[outcome].to_numpy(dtype=float)
    rank = int(np.linalg.matrix_rank(design))
    if rank < design.shape[1]:
        return {**base, "exclusion_reason": "rank_deficient_design"}
    condition_number = float(np.linalg.cond(design))
    base["condition_number"] = condition_number
    condition_limit = float(
        protocol["numerical_gates"]["maximum_design_condition_number"]
    )
    if condition_number > condition_limit:
        return {**base, "exclusion_reason": "condition_number_exceeded"}
    clusters = sample[cluster_column].to_numpy() if cluster_column else None
    fit = _ols(
        response,
        design,
        covariance=covariance,
        clusters=clusters,
        hac_lags=hac_lags,
    )
    return {
        **base,
        "status": "ready",
        "standardized_beta": fit["beta"][1],
        "standard_error": fit["standard_error"][1],
        "test_statistic": fit["test_statistic"][1],
        "inference_degrees_freedom": fit["degrees_freedom"],
        "p_value": fit["p_value"][1],
        "ci_95_low": fit["ci_95_low"][1],
        "ci_95_high": fit["ci_95_high"][1],
        "r_squared": fit["r_squared"],
    }


def _ols(
    response: np.ndarray,
    design: np.ndarray,
    *,
    covariance: str,
    clusters: np.ndarray | None,
    hac_lags: int,
) -> dict[str, np.ndarray | float]:
    beta = np.linalg.solve(design.T @ design, design.T @ response)
    residuals = response - design @ beta
    fitted = design @ beta
    total_sum_squares = float(((response - response.mean()) ** 2).sum())
    residual_sum_squares = float((residuals**2).sum())
    r_squared = 1 - residual_sum_squares / total_sum_squares
    if covariance == "none_descriptive_coefficient_only":
        empty = np.full(len(beta), math.nan)
        return {
            "beta": beta,
            "standard_error": empty,
            "test_statistic": empty,
            "degrees_freedom": math.nan,
            "p_value": empty,
            "ci_95_low": empty,
            "ci_95_high": empty,
            "r_squared": r_squared,
        }
    bread = np.linalg.inv(design.T @ design)
    score = design * residuals[:, None]
    n_observations, n_parameters = design.shape
    if covariance == "record_id_cluster_robust_cr1":
        if clusters is None:
            raise ValueError("cluster covariance requires cluster labels")
        unique_clusters = pd.unique(clusters)
        meat = np.zeros((n_parameters, n_parameters))
        for cluster in unique_clusters:
            cluster_score = score[clusters == cluster].sum(axis=0)
            meat += np.outer(cluster_score, cluster_score)
        cluster_count = len(unique_clusters)
        correction = (cluster_count / (cluster_count - 1)) * (
            (n_observations - 1) / (n_observations - n_parameters)
        )
        covariance_matrix = correction * bread @ meat @ bread
        degrees_freedom = cluster_count - 1
    elif covariance == "newey_west_bartlett":
        meat = score.T @ score
        for lag in range(1, hac_lags + 1):
            weight = 1 - lag / (hac_lags + 1)
            lag_cross = score[lag:].T @ score[:-lag]
            meat += weight * (lag_cross + lag_cross.T)
        correction = n_observations / (n_observations - n_parameters)
        covariance_matrix = correction * bread @ meat @ bread
        degrees_freedom = n_observations - n_parameters
    else:
        raise ValueError(f"unsupported covariance: {covariance}")
    standard_error = np.sqrt(np.maximum(np.diag(covariance_matrix), 0))
    statistic = np.divide(
        beta,
        standard_error,
        out=np.full_like(beta, math.nan),
        where=standard_error > 0,
    )
    p_value = 2 * stats.t.sf(np.abs(statistic), degrees_freedom)
    critical_value = float(stats.t.ppf(0.975, degrees_freedom))
    return {
        "beta": beta,
        "standard_error": standard_error,
        "test_statistic": statistic,
        "p_value": p_value,
        "degrees_freedom": degrees_freedom,
        "ci_95_low": beta - critical_value * standard_error,
        "ci_95_high": beta + critical_value * standard_error,
        "r_squared": r_squared,
        "fitted": fitted,
    }


def _apply_bh(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    ready = result["status"].eq("ready") & result["p_value"].notna()
    p_values = result.loc[ready, "p_value"].sort_values()
    count = len(p_values)
    if count == 0:
        return result
    ranks = np.arange(1, count + 1)
    raw_q = p_values.to_numpy() * count / ranks
    adjusted = np.minimum.accumulate(raw_q[::-1])[::-1].clip(max=1)
    result.loc[p_values.index, "bh_q_value"] = adjusted
    return result


def _mark_candidates(
    pooled: pd.DataFrame, protocol: dict[str, object]
) -> pd.DataFrame:
    result = pooled.copy()
    result["timing_sign_stable"] = False
    timing_count = len(protocol["timing_protocols"])
    for _, group in result.groupby(["feature", "window_sessions"]):
        ready = group.loc[group["status"].eq("ready")]
        stable = (
            len(ready) == timing_count
            and ready["standardized_beta"].ne(0).all()
            and ready["standardized_beta"].gt(0).nunique() == 1
        )
        result.loc[group.index, "timing_sign_stable"] = stable
    threshold = float(protocol["multiplicity"]["reference_fdr"])
    result["candidate_relation"] = (
        result["status"].eq("ready")
        & result["bh_q_value"].le(threshold)
        & result["timing_sign_stable"]
    )
    return result


def _measurement_control(feature: str, protocol: dict[str, object]) -> str:
    mapping = protocol["measurement_control_mapping"]
    if feature.endswith(str(mapping["change_feature_suffix"])):
        return str(mapping["change"])
    return str(mapping["level"])


def _measurement_controls(protocol: dict[str, object]) -> list[str]:
    mapping = protocol["measurement_control_mapping"]
    return [str(mapping["level"]), str(mapping["change"])]


def _validate_inputs(
    panel: pd.DataFrame, protocol: dict[str, object]
) -> None:
    if protocol.get("status") != "frozen_before_adjusted_market_relationships":
        raise ValueError("adjusted relation protocol is not frozen")
    if protocol.get("evidence_status") != "post_descriptive_exploratory":
        raise ValueError("adjusted evidence must be labelled post-descriptive")
    rules = protocol.get("reporting_rules", {})
    if rules.get("portfolio_construction_allowed") is not False:
        raise ValueError("protocol must prohibit portfolio construction")
    required = {
        "protocol",
        "record_id",
        "period_end",
        "activation_date",
        "window_sessions",
        "symbol",
        "asset_group",
        "point_in_time_status",
        "forward_return",
        *[str(value) for value in protocol["market_controls"]],
        *[str(value) for value in protocol["primary_features"]],
        *_measurement_controls(protocol),
    }
    missing = sorted(required - set(panel.columns))
    if missing:
        raise ValueError(f"market relation panel missing columns: {', '.join(missing)}")
    if panel.duplicated(
        ["protocol", "record_id", "window_sessions", "symbol"]
    ).any():
        raise ValueError("market relation panel contains duplicate outcome rows")
    expected_protocols = set(str(value) for value in protocol["timing_protocols"])
    expected_windows = set(
        int(value) for value in protocol["forward_windows_reference_sessions"]
    )
    if set(panel["protocol"]) != expected_protocols:
        raise ValueError("panel timing protocols do not match adjusted protocol")
    if set(panel["window_sessions"].astype(int)) != expected_windows:
        raise ValueError("panel windows do not match adjusted protocol")
