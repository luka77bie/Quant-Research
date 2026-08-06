from __future__ import annotations

from pathlib import Path

import pandas as pd

from narrative_regime.data.validation import normalize_market_frame

MAX_RETURN_MAE = 1e-4
MIN_RETURN_CORRELATION = 0.999
VOLUME_RATIO_LOWER = 0.95
VOLUME_RATIO_UPPER = 1.05


def compare_provider_caches(
    root: Path,
    left_provider: str,
    right_provider: str,
    symbols: list[str],
) -> pd.DataFrame:
    """Compare independently cached providers without merging their histories."""
    records = [
        _compare_symbol(root, left_provider, right_provider, symbol)
        for symbol in symbols
    ]
    return pd.DataFrame(records)


def _compare_symbol(
    root: Path,
    left_provider: str,
    right_provider: str,
    symbol: str,
) -> dict[str, object]:
    left = _read_cache(root, left_provider, symbol)
    right = _read_cache(root, right_provider, symbol)
    merged = left.merge(
        right,
        on="date",
        how="outer",
        suffixes=("_left", "_right"),
        indicator=True,
    ).sort_values("date")
    overlap = merged[merged["_merge"] == "both"].copy()
    left_only = int((merged["_merge"] == "left_only").sum())
    right_only = int((merged["_merge"] == "right_only").sum())
    issues: list[str] = []
    if left_only or right_only:
        issues.append(f"date mismatch: left_only={left_only} right_only={right_only}")
    if len(overlap) < 2:
        issues.append("fewer than two overlapping observations")
        return _record(
            symbol=symbol,
            left_provider=left_provider,
            right_provider=right_provider,
            left_rows=len(left),
            right_rows=len(right),
            overlap_rows=len(overlap),
            left_only_dates=left_only,
            right_only_dates=right_only,
            status="blocked",
            issues="; ".join(issues),
        )

    left_returns = overlap["close_left"].pct_change()
    right_returns = overlap["close_right"].pct_change()
    return_difference = (left_returns - right_returns).abs().dropna()
    return_mae = float(return_difference.mean())
    return_p99 = float(return_difference.quantile(0.99))
    return_max = float(return_difference.max())
    return_correlation = float(left_returns.corr(right_returns))
    close_mae = float((overlap["close_left"] - overlap["close_right"]).abs().mean())

    valid_volume = overlap[["volume_left", "volume_right"]].dropna()
    valid_volume = valid_volume[valid_volume["volume_right"] != 0]
    volume_ratio_median = (
        float((valid_volume["volume_left"] / valid_volume["volume_right"]).median())
        if not valid_volume.empty
        else None
    )
    if return_mae > MAX_RETURN_MAE:
        issues.append(f"return MAE {return_mae:.6g} exceeds {MAX_RETURN_MAE:.6g}")
    if return_correlation < MIN_RETURN_CORRELATION:
        issues.append(
            f"return correlation {return_correlation:.6g} below "
            f"{MIN_RETURN_CORRELATION:.6g}"
        )
    if volume_ratio_median is None:
        issues.append("no comparable nonzero volume observations")
    elif not VOLUME_RATIO_LOWER <= volume_ratio_median <= VOLUME_RATIO_UPPER:
        issues.append(f"volume ratio median {volume_ratio_median:.6g} differs from 1")

    return _record(
        symbol=symbol,
        left_provider=left_provider,
        right_provider=right_provider,
        left_rows=len(left),
        right_rows=len(right),
        overlap_rows=len(overlap),
        left_only_dates=left_only,
        right_only_dates=right_only,
        close_mae=close_mae,
        return_mae=return_mae,
        return_p99=return_p99,
        return_max=return_max,
        return_correlation=return_correlation,
        volume_ratio_median=volume_ratio_median,
        status="ready" if not issues else "blocked",
        issues="; ".join(issues),
    )


def _read_cache(root: Path, provider: str, symbol: str) -> pd.DataFrame:
    path = root / "data" / "raw" / provider / f"{symbol}.csv"
    if not path.exists():
        raise ValueError(f"missing provider cache: {path}")
    return normalize_market_frame(pd.read_csv(path))


def _record(**values: object) -> dict[str, object]:
    defaults: dict[str, object] = {
        "close_mae": None,
        "return_mae": None,
        "return_p99": None,
        "return_max": None,
        "return_correlation": None,
        "volume_ratio_median": None,
    }
    metrics = {key: values.get(key, value) for key, value in defaults.items()}
    return {**values, **metrics}
