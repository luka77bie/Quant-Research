from __future__ import annotations

from pathlib import Path

import pandas as pd

from narrative_regime.narrative.archive import validate_catalog

ROOT = Path(__file__).resolve().parents[1]


def test_committed_pboc_catalog_covers_every_2018_2025_quarter() -> None:
    catalog = pd.read_csv(
        ROOT / "configs/pboc_mpr_catalog.csv",
        dtype=str,
        keep_default_na=False,
    )
    sources = pd.read_csv(
        ROOT / "configs/narrative_sources.csv",
        dtype=str,
        keep_default_na=False,
    )

    validated = validate_catalog(catalog, sources)
    expected = pd.date_range(
        "2018-03-31", "2025-12-31", freq=pd.offsets.QuarterEnd()
    )

    assert len(validated) == 32
    assert validated["period_end"].tolist() == expected.tolist()
    assert validated["expected_document_sha256"].is_unique
    delays = validated["available_at"].sub(validated["published_at"])
    assert delays.dt.total_seconds().eq(24 * 60 * 60).all()
