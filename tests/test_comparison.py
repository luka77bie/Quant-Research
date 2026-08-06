from __future__ import annotations

from pathlib import Path

import pandas as pd

from narrative_regime.data.comparison import compare_provider_caches


def _write_cache(
    root: Path,
    provider: str,
    dates: list[str],
    closes: list[float],
    volumes: list[int] | None = None,
) -> None:
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": closes,
            "high": [value + 0.1 for value in closes],
            "low": [value - 0.1 for value in closes],
            "close": closes,
            "volume": volumes or [100] * len(dates),
            "amount": [1000] * len(dates),
        }
    )
    path = root / "data" / "raw" / provider / "510300.csv"
    path.parent.mkdir(parents=True)
    frame.to_csv(path, index=False)


def test_comparison_accepts_equivalent_provider_caches(tmp_path: Path) -> None:
    dates = ["2024-01-02", "2024-01-03", "2024-01-04"]
    _write_cache(tmp_path, "left", dates, [10.0, 10.1, 10.2])
    _write_cache(tmp_path, "right", dates, [20.0, 20.2, 20.4])

    report = compare_provider_caches(tmp_path, "left", "right", ["510300"])

    assert report.loc[0, "status"] == "ready"
    assert report.loc[0, "return_correlation"] == 1.0
    assert report.loc[0, "volume_ratio_median"] == 1.0


def test_comparison_blocks_date_and_return_disagreement(tmp_path: Path) -> None:
    _write_cache(
        tmp_path,
        "left",
        ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
        [10.0, 10.1, 10.2, 10.3],
    )
    _write_cache(
        tmp_path,
        "right",
        ["2024-01-02", "2024-01-03", "2024-01-04"],
        [10.0, 9.0, 11.0],
    )

    report = compare_provider_caches(tmp_path, "left", "right", ["510300"])

    assert report.loc[0, "status"] == "blocked"
    assert "date mismatch" in report.loc[0, "issues"]
    assert "return MAE" in report.loc[0, "issues"]
