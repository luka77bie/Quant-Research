from __future__ import annotations

import pandas as pd

from narrative_regime.macro.pilot import audit_macro_release_pilot


def _catalog() -> pd.DataFrame:
    rows = []
    for dimension in ["growth", "inflation", "liquidity"]:
        for month in range(1, 5):
            rows.append(
                {
                    "record_id": f"{dimension}-{month}",
                    "dimension": dimension,
                    "series_id": f"{dimension}_series",
                    "series_name": f"{dimension} series",
                    "period": f"2024-{month:02d}",
                    "release_at": f"2024-{month + 1:02d}-10T09:30:00+08:00",
                    "source_url": "https://www.stats.gov.cn/example.html",
                    "source_record_type": "original_release_page",
                    "value": float(month),
                    "unit": "index",
                    "seasonal_adjustment": "not_seasonally_adjusted",
                    "release_value_status": "official_release_value",
                    "revision_status": "not_stated",
                    "historical_snapshot_url": "",
                    "strict_point_in_time_status": "provisional_no_snapshot",
                    "review_status": "publication_record_ready",
                }
            )
    return pd.DataFrame(rows)


def test_macro_pilot_passes_complete_official_catalog() -> None:
    result = audit_macro_release_pilot(_catalog())

    assert result.summary["macro_release_pilot_gate"] == (
        "pass_publication_record_only"
    )
    assert result.summary["ready_records"] == 12
    assert result.summary["strict_point_in_time_verified_records"] == 0
    assert result.summary["etf_returns_read"] is False


def test_macro_pilot_blocks_non_official_source() -> None:
    catalog = _catalog()
    catalog.loc[0, "source_url"] = "https://example.com/macro"

    result = audit_macro_release_pilot(catalog)

    assert result.summary["macro_release_pilot_gate"] == "blocked"
    assert result.audit.loc[0, "failure_reasons"] == "official_domain"
