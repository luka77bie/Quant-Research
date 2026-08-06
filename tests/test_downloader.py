from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

from narrative_regime.data.downloader import DownloadManager
from narrative_regime.data.models import FetchRequest


class FakeProvider:
    def __init__(self, name: str, failures: int = 0) -> None:
        self.name = name
        self.failures = failures
        self.calls = 0

    def fetch(self, request: FetchRequest) -> pd.DataFrame:
        self.calls += 1
        if self.calls <= self.failures:
            raise TimeoutError("simulated throttle")
        return _frame()


def _frame() -> pd.DataFrame:
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


def test_falls_back_after_provider_retries(tmp_path: Path) -> None:
    primary = FakeProvider("primary", failures=3)
    fallback = FakeProvider("fallback")
    manager = DownloadManager(
        tmp_path,
        [primary, fallback],
        attempts=3,
        base_delay_seconds=0,
        inter_symbol_delay_seconds=0,
        sleep=lambda _: None,
    )

    result = manager.download_one(
        FetchRequest("510300", date(2024, 1, 1), date(2024, 1, 31))
    )

    assert result.status == "downloaded"
    assert result.provider == "fallback"
    assert primary.calls == 3
    assert fallback.calls == 1
    assert result.cache_path and result.cache_path.exists()


def test_identical_request_uses_validated_cache(tmp_path: Path) -> None:
    provider = FakeProvider("primary")
    manager = DownloadManager(
        tmp_path,
        [provider],
        inter_symbol_delay_seconds=0,
        sleep=lambda _: None,
    )
    request = FetchRequest("510300", date(2024, 1, 1), date(2024, 1, 31))

    first = manager.download_one(request)
    second = manager.download_one(request)

    assert first.status == "downloaded"
    assert second.status == "cached"
    assert provider.calls == 1


def test_corrupt_metadata_forces_refresh(tmp_path: Path) -> None:
    provider = FakeProvider("primary")
    manager = DownloadManager(
        tmp_path,
        [provider],
        inter_symbol_delay_seconds=0,
        sleep=lambda _: None,
    )
    request = FetchRequest("510300", date(2024, 1, 1), date(2024, 1, 31))
    first = manager.download_one(request)
    assert first.cache_path
    first.cache_path.with_suffix(".meta.json").write_text("not-json")

    second = manager.download_one(request)

    assert second.status == "downloaded"
    assert provider.calls == 2


def test_manifest_keeps_success_and_failure_records(tmp_path: Path) -> None:
    provider = FakeProvider("primary", failures=10)
    manager = DownloadManager(
        tmp_path,
        [provider],
        attempts=1,
        base_delay_seconds=0,
        inter_symbol_delay_seconds=0,
        sleep=lambda _: None,
    )

    result = manager.download_one(
        FetchRequest("510300", date(2024, 1, 1), date(2024, 1, 31))
    )

    assert result.status == "failed"
    manifest = tmp_path / "data" / "manifests" / "downloads.jsonl"
    records = [json.loads(line) for line in manifest.read_text().splitlines()]
    assert len(records) == 2
    assert records[0]["event"] == "provider_attempt"
    assert records[0]["status"] == "failed"
    assert "simulated throttle" in records[0]["error"]
    assert records[1]["event"] == "symbol_result"
    assert records[1]["result"]["status"] == "failed"


def test_partial_primary_falls_back_to_complete_provider(tmp_path: Path) -> None:
    class PartialProvider(FakeProvider):
        def fetch(self, request: FetchRequest) -> pd.DataFrame:
            self.calls += 1
            frame = _frame()
            frame["date"] = ["2024-01-20", "2024-01-21", "2024-01-22"]
            return frame

    primary = PartialProvider("primary")
    fallback = FakeProvider("fallback")
    manager = DownloadManager(
        tmp_path,
        [primary, fallback],
        attempts=1,
        base_delay_seconds=0,
        inter_symbol_delay_seconds=0,
        sleep=lambda _: None,
    )

    result = manager.download_one(
        FetchRequest("510300", date(2024, 1, 1), date(2024, 1, 31))
    )

    assert result.status == "downloaded"
    assert result.provider == "fallback"
    assert primary.calls == 1
    assert fallback.calls == 1
    primary_metadata = json.loads(
        (tmp_path / "data/raw/primary/510300.meta.json").read_text()
    )
    assert primary_metadata["status"] == "partial"


def test_all_partial_providers_return_visible_partial_result(tmp_path: Path) -> None:
    class PartialProvider(FakeProvider):
        def fetch(self, request: FetchRequest) -> pd.DataFrame:
            self.calls += 1
            frame = _frame()
            frame["date"] = ["2024-01-20", "2024-01-21", "2024-01-22"]
            return frame

    manager = DownloadManager(
        tmp_path,
        [PartialProvider("primary"), PartialProvider("fallback")],
        attempts=1,
        inter_symbol_delay_seconds=0,
        sleep=lambda _: None,
    )

    result = manager.download_one(
        FetchRequest("510300", date(2024, 1, 1), date(2024, 1, 31))
    )

    assert result.status == "partial"
    assert result.coverage_issues


def test_cache_checksum_mismatch_forces_refresh(tmp_path: Path) -> None:
    provider = FakeProvider("primary")
    manager = DownloadManager(
        tmp_path,
        [provider],
        inter_symbol_delay_seconds=0,
        sleep=lambda _: None,
    )
    request = FetchRequest("510300", date(2024, 1, 1), date(2024, 1, 31))
    first = manager.download_one(request)
    assert first.cache_path
    first.cache_path.write_text(first.cache_path.read_text() + "\n")

    second = manager.download_one(request)

    assert second.status == "downloaded"
    assert provider.calls == 2


def test_batch_circuit_breaker_skips_remaining_symbols(tmp_path: Path) -> None:
    provider = FakeProvider("primary", failures=10)
    manager = DownloadManager(
        tmp_path,
        [provider],
        attempts=1,
        max_consecutive_failures=2,
        inter_symbol_delay_seconds=0,
        sleep=lambda _: None,
    )
    requests = [
        FetchRequest(symbol, date(2024, 1, 1), date(2024, 1, 31))
        for symbol in ["A", "B", "C", "D"]
    ]

    results = manager.download_many(requests)

    assert [result.status for result in results] == [
        "failed",
        "failed",
        "skipped",
        "skipped",
    ]
    assert provider.calls == 2
    manifest = tmp_path / "data" / "manifests" / "downloads.jsonl"
    records = [json.loads(line) for line in manifest.read_text().splitlines()]
    symbol_results = [
        record for record in records if record["event"] == "symbol_result"
    ]
    assert len(symbol_results) == 4
