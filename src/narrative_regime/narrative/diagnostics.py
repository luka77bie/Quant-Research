from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class FeatureDiagnosticResult:
    distribution: pd.DataFrame
    missingness: pd.DataFrame
    persistence: pd.DataFrame
    pearson: pd.DataFrame
    spearman: pd.DataFrame
    high_correlation_pairs: pd.DataFrame
    summary: dict[str, object]


def audit_policy_features(features: pd.DataFrame) -> FeatureDiagnosticResult:
    """Audit all numeric policy features without market or return data."""
    if len(features) < 30:
        raise ValueError("feature diagnostics require at least 30 records")
    if "period_end" not in features:
        raise ValueError("features missing period_end")
    ordered = features.copy()
    ordered["period_end"] = pd.to_datetime(ordered["period_end"], errors="raise")
    ordered = ordered.sort_values("period_end").reset_index(drop=True)
    numeric = ordered.select_dtypes(include="number")
    if numeric.empty:
        raise ValueError("features contain no numeric columns")

    infinite_counts = np.isinf(numeric).sum()
    clean_numeric = numeric.replace([np.inf, -np.inf], np.nan)
    distribution_rows = []
    missing_rows = []
    persistence_rows = []
    for column in numeric.columns:
        original = numeric[column]
        series = clean_numeric[column]
        valid = series.dropna()
        expected_missing = 1 if _first_observation_missing_expected(column) else 0
        actual_missing = int(original.isna().sum())
        distribution_rows.append(
            {
                "feature": column,
                "observations": len(valid),
                "unique_values": int(valid.nunique()),
                "nonzero_observations": int(valid.ne(0).sum()),
                "mean": valid.mean(),
                "standard_deviation": valid.std(),
                "minimum": valid.min(),
                "p25": valid.quantile(0.25),
                "median": valid.median(),
                "p75": valid.quantile(0.75),
                "maximum": valid.max(),
            }
        )
        missing_rows.append(
            {
                "feature": column,
                "missing_observations": actual_missing,
                "expected_missing_observations": expected_missing,
                "unexpected_missing_observations": max(
                    actual_missing - expected_missing, 0
                ),
                "infinite_observations": int(infinite_counts[column]),
            }
        )
        lagged = pd.concat(
            [series.rename("current"), series.shift(1).rename("prior")], axis=1
        ).dropna()
        persistence_rows.append(
            {
                "feature": column,
                "pairs": len(lagged),
                "lag1_pearson": _safe_correlation(
                    lagged["current"], lagged["prior"]
                ),
                "lag1_spearman": _safe_correlation(
                    lagged["current"], lagged["prior"], rank=True
                ),
            }
        )

    distribution = pd.DataFrame(distribution_rows)
    missingness = pd.DataFrame(missing_rows)
    persistence = pd.DataFrame(persistence_rows)
    pearson = clean_numeric.corr(method="pearson")
    spearman = clean_numeric.rank().corr(method="pearson")
    high_pairs = _high_correlation_pairs(pearson, spearman)
    zero_variance = distribution.loc[
        distribution["unique_values"].le(1), "feature"
    ].tolist()
    unexpected_missing = int(missingness["unexpected_missing_observations"].sum())
    infinite = int(missingness["infinite_observations"].sum())
    summary = {
        "records": len(ordered),
        "numeric_features": len(numeric.columns),
        "expected_missing_observations": int(
            missingness["expected_missing_observations"].sum()
        ),
        "actual_missing_observations": int(
            missingness["missing_observations"].sum()
        ),
        "unexpected_missing_observations": unexpected_missing,
        "infinite_observations": infinite,
        "zero_variance_features": zero_variance,
        "absolute_spearman_ge_0_90_pairs": len(high_pairs),
        "diagnostic_gate": (
            "pass" if unexpected_missing == 0 and infinite == 0 else "blocked"
        ),
        "market_data_used": False,
        "return_data_used": False,
        "feature_selection_performed": False,
        "research_use": "exploratory_only",
    }
    return FeatureDiagnosticResult(
        distribution,
        missingness,
        persistence,
        pearson,
        spearman,
        high_pairs,
        summary,
    )


def _first_observation_missing_expected(feature: str) -> bool:
    direct = feature in {"prior_section_similarity", "section_novelty"}
    return direct or feature.endswith("_change_qoq")


def _safe_correlation(
    left: pd.Series,
    right: pd.Series,
    *,
    rank: bool = False,
) -> float:
    if len(left) < 2 or left.nunique() < 2 or right.nunique() < 2:
        return float("nan")
    if rank:
        left = left.rank()
        right = right.rank()
    return float(left.corr(right))


def _high_correlation_pairs(
    pearson: pd.DataFrame,
    spearman: pd.DataFrame,
    threshold: float = 0.90,
) -> pd.DataFrame:
    rows = []
    columns = list(spearman.columns)
    for left_index, left in enumerate(columns):
        for right in columns[left_index + 1 :]:
            spearman_value = spearman.loc[left, right]
            if pd.notna(spearman_value) and abs(spearman_value) >= threshold:
                rows.append(
                    {
                        "left_feature": left,
                        "right_feature": right,
                        "pearson": pearson.loc[left, right],
                        "spearman": spearman_value,
                    }
                )
    return pd.DataFrame(
        rows,
        columns=["left_feature", "right_feature", "pearson", "spearman"],
    ).sort_values("spearman", key=lambda values: values.abs(), ascending=False)
