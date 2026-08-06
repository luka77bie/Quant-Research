from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from narrative_regime.data.downloader import DownloadManager
from narrative_regime.data.models import FetchRequest
from narrative_regime.data.panel import (
    build_common_sample,
    validate_availability_metadata,
    validate_calendar_exceptions,
)


class PanelProvider:
    name = "test"

    def __init__(self, dates: dict[str, list[str]]) -> None:
        self.dates = dates

    def fetch(self, request: FetchRequest) -> pd.DataFrame:
        dates = self.dates[request.symbol]
        close = [10.0 + index for index in range(len(dates))]
        return pd.DataFrame(
            {
                "date": dates,
                "open": close,
                "high": [value + 0.5 for value in close],
                "low": [value - 0.5 for value in close],
                "close": close,
                "volume": [100] * len(dates),
                "amount": [1000] * len(dates),
            }
        )


def _universe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "symbol": ["REF", "NEW"],
            "asset_group": ["broad", "sector"],
            "available_from": ["2020-01-01", "2020-01-05"],
        }
    )


def _sources() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "symbol": ["REF", "NEW"],
            "listing_date": ["2020-01-01", "2020-01-05"],
            "venue": ["SSE", "SSE"],
            "source": ["official", "official"],
            "source_url": ["https://example.test", "https://example.test"],
            "verified_at": ["2026-08-06", "2026-08-06"],
        }
    )


def _exceptions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "symbol": ["NEW"],
            "date": ["2020-01-08"],
            "reason": ["temporary_suspension"],
            "evidence_left_url": ["https://left.example.test"],
            "evidence_right_url": ["https://right.example.test"],
            "verified_at": ["2026-08-06"],
        }
    )


def _download_caches(tmp_path: Path, new_dates: list[str]) -> None:
    reference_dates = [
        "2020-01-02",
        "2020-01-03",
        "2020-01-05",
        "2020-01-06",
        "2020-01-07",
        "2020-01-08",
        "2020-01-09",
        "2020-01-10",
    ]
    manager = DownloadManager(
        tmp_path,
        [PanelProvider({"REF": reference_dates, "NEW": new_dates})],
        inter_symbol_delay_seconds=0,
        sleep=lambda _: None,
    )
    results = manager.download_many(
        [
            FetchRequest("REF", date(2020, 1, 1), date(2020, 1, 10)),
            FetchRequest("NEW", date(2020, 1, 5), date(2020, 1, 10)),
        ]
    )
    assert all(result.status == "downloaded" for result in results)


def test_availability_sources_must_match_universe() -> None:
    sources = _sources()
    sources.loc[sources["symbol"] == "NEW", "listing_date"] = "2020-01-06"

    with pytest.raises(ValueError, match="differs"):
        validate_availability_metadata(_universe(), sources)


def test_build_common_sample_uses_dynamic_listing_eligibility(tmp_path: Path) -> None:
    new_dates = [
        "2020-01-05",
        "2020-01-06",
        "2020-01-07",
        "2020-01-08",
        "2020-01-09",
        "2020-01-10",
    ]
    _download_caches(tmp_path, new_dates)

    result = build_common_sample(
        root=tmp_path,
        provider="test",
        universe=_universe(),
        start=date(2020, 1, 1),
        end=date(2020, 1, 10),
        reference_symbol="REF",
    )

    assert result.ready
    assert len(result.sample[result.sample["symbol"] == "REF"]) == 8
    assert len(result.sample[result.sample["symbol"] == "NEW"]) == 6
    assert result.sample["source_provider"].unique().tolist() == ["test"]


def test_build_common_sample_blocks_missing_exchange_session(tmp_path: Path) -> None:
    new_dates = [
        "2020-01-05",
        "2020-01-06",
        "2020-01-07",
        "2020-01-09",
        "2020-01-10",
    ]
    _download_caches(tmp_path, new_dates)

    result = build_common_sample(
        root=tmp_path,
        provider="test",
        universe=_universe(),
        start=date(2020, 1, 1),
        end=date(2020, 1, 10),
        reference_symbol="REF",
    )

    assert not result.ready
    assert result.sample.empty
    new_audit = result.panel_audit.set_index("symbol").loc["NEW"]
    assert new_audit["status"] == "misaligned"
    assert new_audit["missing_dates"] == 1


def test_verified_no_trade_date_creates_explicit_stale_mark(tmp_path: Path) -> None:
    new_dates = [
        "2020-01-05",
        "2020-01-06",
        "2020-01-07",
        "2020-01-09",
        "2020-01-10",
    ]
    _download_caches(tmp_path, new_dates)

    result = build_common_sample(
        root=tmp_path,
        provider="test",
        universe=_universe(),
        start=date(2020, 1, 1),
        end=date(2020, 1, 10),
        reference_symbol="REF",
        calendar_exceptions=_exceptions(),
    )

    assert result.ready
    marked = result.sample[
        (result.sample["symbol"] == "NEW")
        & (result.sample["date"] == pd.Timestamp("2020-01-08"))
    ].iloc[0]
    assert marked["observation_status"] == "verified_no_trade"
    assert not bool(marked["is_tradable"])
    assert marked["volume"] == 0
    assert marked["close"] == 12.0
    new_audit = result.panel_audit.set_index("symbol").loc["NEW"]
    assert new_audit["verified_no_trade_dates"] == 1


def test_calendar_exception_rejects_unknown_symbol() -> None:
    exceptions = _exceptions()
    exceptions.loc[0, "symbol"] = "UNKNOWN"

    with pytest.raises(ValueError, match="unknown symbols"):
        validate_calendar_exceptions(_universe(), exceptions)
