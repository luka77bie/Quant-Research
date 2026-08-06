from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from narrative_regime.data.audit import audit_provider_cache
from narrative_regime.data.downloader import DownloadManager
from narrative_regime.data.models import FetchRequest


class CompleteProvider:
    name = "test"

    def fetch(self, request: FetchRequest) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "date": ["2024-01-02", "2024-01-15", "2024-01-29"],
                "open": [10.0, 10.2, 10.5],
                "high": [11.0, 11.2, 11.5],
                "low": [9.5, 9.8, 10.0],
                "close": [10.5, 10.8, 11.0],
                "volume": [100, 110, 120],
                "amount": [1000, 1188, 1320],
            }
        )


def test_audit_accepts_intact_validated_cache(tmp_path: Path) -> None:
    manager = DownloadManager(
        tmp_path,
        [CompleteProvider()],
        inter_symbol_delay_seconds=0,
        sleep=lambda _: None,
    )
    manager.download_one(
        FetchRequest("510300", date(2024, 1, 1), date(2024, 1, 31))
    )

    report = audit_provider_cache(tmp_path, "test", ["510300"])

    assert report.loc[0, "audit_status"] == "ready"
    assert bool(report.loc[0, "checksum_ok"])
    assert report.loc[0, "rows"] == 3


def test_audit_reports_missing_and_tampered_cache(tmp_path: Path) -> None:
    manager = DownloadManager(
        tmp_path,
        [CompleteProvider()],
        inter_symbol_delay_seconds=0,
        sleep=lambda _: None,
    )
    result = manager.download_one(
        FetchRequest("510300", date(2024, 1, 1), date(2024, 1, 31))
    )
    assert result.cache_path
    original = result.cache_path.read_text()
    first_data_row = original.splitlines()[1]
    result.cache_path.write_text(original + first_data_row + "\n")

    report = audit_provider_cache(tmp_path, "test", ["510300", "510500"])

    assert report.loc[0, "audit_status"] == "invalid"
    assert "checksum mismatch" in report.loc[0, "issues"]
    assert "duplicate dates" in report.loc[0, "issues"]
    assert report.loc[1, "audit_status"] == "missing"
